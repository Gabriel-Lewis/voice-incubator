#!/usr/bin/env python3
"""Export a NeMo FastConformer hybrid (transducer + CTC) checkpoint the way
the English parakeet-tdt_ctc-110m is laid out in models/:

- ``models/speech-to-phrase/<name>/``: the CTC branch, ``model.onnx`` and
  ``tokens.txt``, for adapt-ctc's ``CtcModel``; ``<name>-int8`` beside it;
- ``models/<name>-transducer/``: the transducer branch, ``encoder.onnx``,
  ``decoder.onnx``, ``joiner.onnx`` and ``tokens.txt``, for
  ``adapt_ctc/tdt.py`` (sherpa-onnx); ``-int8`` beside it with only the
  encoder quantized.

Both int8 builds are what the English ones are: dynamic, int8 weights in the
MatMuls only (scripts/quantize_tdt.py), the convolutions left float.
sherpa-onnx's export scripts quantize the convolutions too, in uint8: 132 MB
rather than 172, and a greedy CTC transcript that drifts from NeMo's.

It follows sherpa-onnx's scripts/nemo/fast-conformer-hybrid-transducer-ctc,
without the streaming caches -- then checks the CTC export against NeMo on
``--wav``: the same features through both, the largest difference in log
probability, and both greedy transcripts (int8 too).

Needs NeMo, which the app does not: in a venv of its own, on a Python with
its headers (uv's own; texterrors builds against them):

    uv venv -p 3.11 --python-preference only-managed nemo-venv
    VIRTUAL_ENV=nemo-venv uv pip install --index-strategy unsafe-best-match \\
        --extra-index-url https://download.pytorch.org/whl/cpu \\
        "torch==2.6.0+cpu" "nemo_toolkit[asr]==2.3.*" onnx onnxruntime onnxscript
    nemo-venv/bin/python scripts/export_nemo_hybrid.py \\
        stt_de_fastconformer_hybrid_large_pc.nemo --wav some-german.wav
"""

from __future__ import annotations

import argparse
import shutil
import time
from pathlib import Path

import numpy as np
import onnx
import onnxruntime as ort
import torch
from onnxruntime.quantization import QuantType, quantize_dynamic

ROOT = Path(__file__).resolve().parent.parent


def add_metadata(path: Path, metadata: dict[str, object]) -> None:
    model = onnx.load(path)
    del model.metadata_props[:]
    for key, value in metadata.items():
        model.metadata_props.add(key=key, value=str(value))
    onnx.save(model, path)


def write_tokens(path: Path, vocabulary: list[str]) -> None:
    with open(path, "w", encoding="utf-8") as tokens:
        for index, piece in enumerate(vocabulary):
            tokens.write(f"{piece} {index}\n")
        tokens.write(f"<blk> {len(vocabulary)}\n")


def quantize(src: Path, dst: Path) -> None:
    quantize_dynamic(
        src,
        dst,
        weight_type=QuantType.QInt8,
        op_types_to_quantize=["MatMul"],
        extra_options={"MatMulConstBOnly": True},
    )


def greedy(log_probs: np.ndarray, vocabulary: list[str]) -> str:
    blank = len(vocabulary)
    pieces, previous = [], blank
    for token in log_probs.argmax(axis=-1):
        if token != previous and token != blank:
            pieces.append(vocabulary[token])
        previous = token
    return "".join(pieces).replace("▁", " ").strip()


@torch.no_grad()
def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("nemo", type=Path, help="the hybrid checkpoint (.nemo)")
    parser.add_argument("--name", help="directory name (default: the checkpoint's)")
    parser.add_argument("--models", type=Path, default=ROOT / "models")
    parser.add_argument("--wav", type=Path, help="16 kHz mono audio to check the CTC export on")
    args = parser.parse_args()

    import nemo.collections.asr as nemo_asr  # pylint: disable=import-outside-toplevel

    name = args.name or args.nemo.stem
    model = nemo_asr.models.ASRModel.restore_from(str(args.nemo), map_location="cpu")
    model.eval()
    vocabulary = list(model.joint.vocabulary)
    normalize = model.cfg.preprocessor.normalize
    common = {
        "vocab_size": model.decoder.vocab_size,
        "normalize_type": "" if normalize == "NA" else normalize,
        "subsampling_factor": model.cfg.encoder.subsampling_factor,
        "model_type": type(model).__name__,
        "version": "1",
        "model_author": "NeMo",
        "url": f"https://huggingface.co/nvidia/{args.nemo.stem}",
    }

    # The CTC branch: encoder and CTC decoder, one model.
    ctc_dir = args.models / "speech-to-phrase" / name
    ctc_int8 = ctc_dir.with_name(f"{name}-int8")
    for directory in (ctc_dir, ctc_int8):
        directory.mkdir(parents=True, exist_ok=True)
        write_tokens(directory / "tokens.txt", vocabulary)
    model.change_decoding_strategy(decoder_type="ctc")
    model.set_export_config({"decoder_type": "ctc"})
    started = time.monotonic()
    model.export(str(ctc_dir / "model.onnx"))
    add_metadata(ctc_dir / "model.onnx", {**common, "comment": "Only the CTC branch is exported"})
    quantize(ctc_dir / "model.onnx", ctc_int8 / "model.onnx")
    print(f"CTC: {_mb(ctc_dir / 'model.onnx')} -> {_mb(ctc_int8 / 'model.onnx')} int8 ({time.monotonic() - started:.0f}s)")

    # The transducer branch: encoder, prediction network, joiner.
    rnnt_dir = args.models / f"{name}-transducer"
    rnnt_int8 = rnnt_dir.with_name(f"{name}-transducer-int8")
    for directory in (rnnt_dir, rnnt_int8):
        directory.mkdir(parents=True, exist_ok=True)
        write_tokens(directory / "tokens.txt", vocabulary)
    model.change_decoding_strategy(decoder_type="rnnt")
    model.set_export_config({"decoder_type": "rnnt"})
    started = time.monotonic()
    model.encoder.export(str(rnnt_dir / "encoder.onnx"))
    model.decoder.export(str(rnnt_dir / "decoder.onnx"))
    model.joint.export(str(rnnt_dir / "joiner.onnx"))
    add_metadata(
        rnnt_dir / "encoder.onnx",
        {
            **common,
            "pred_rnn_layers": model.decoder.pred_rnn_layers,
            "pred_hidden": model.decoder.pred_hidden,
            "comment": "Only the transducer branch is exported",
        },
    )
    quantize(rnnt_dir / "encoder.onnx", rnnt_int8 / "encoder.onnx")
    for part in ("decoder", "joiner"):
        shutil.copy2(rnnt_dir / f"{part}.onnx", rnnt_int8 / f"{part}.onnx")
    print(
        f"transducer: encoder {_mb(rnnt_dir / 'encoder.onnx')} -> {_mb(rnnt_int8 / 'encoder.onnx')} int8 "
        f"({time.monotonic() - started:.0f}s)"
    )

    if args.wav:
        check(model, vocabulary, args.wav, [ctc_dir / "model.onnx", ctc_int8 / "model.onnx"])


def check(model, vocabulary: list[str], wav: Path, exports: list[Path]) -> None:
    """NeMo's CTC log probabilities against each export's, on the same
    features (dither off)."""
    import soundfile  # pylint: disable=import-outside-toplevel

    audio, rate = soundfile.read(wav, dtype="float32")
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    if rate != 16000:
        import librosa  # pylint: disable=import-outside-toplevel

        audio = librosa.resample(audio, orig_sr=rate, target_sr=16000)
    model.preprocessor.featurizer.dither = 0.0
    signal = torch.from_numpy(audio)[None]
    feats, feat_len = model.preprocessor(input_signal=signal, length=torch.tensor([signal.shape[1]]))
    encoded, encoded_len = model.encoder(audio_signal=feats, length=feat_len)
    reference = model.ctc_decoder(encoder_output=encoded)[0, : encoded_len[0]].numpy()
    print(f"NeMo:  {greedy(reference, vocabulary)}")
    for path in exports:
        session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
        inputs = session.get_inputs()
        out = session.run(None, {inputs[0].name: feats.numpy(), inputs[1].name: feat_len.numpy()})[0][0]
        out = out[: len(reference)]
        print(f"{path.parent.name}: max |diff| {np.abs(out - reference).max():.4f}: {greedy(out, vocabulary)}")


def _mb(path: Path) -> str:
    return f"{path.stat().st_size / 1e6:.0f} MB"


if __name__ == "__main__":
    main()
