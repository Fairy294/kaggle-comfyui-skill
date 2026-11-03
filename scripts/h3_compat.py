"""Opt-in pinned H3 two-T4 profile. Original adaptation, not upstream sources.

Derived from mechanisms used by the prior dedicated project. The old complete
runs do not certify this refactored runner. All patches are source-anchor
checked before any file is written; any version drift fails closed.
"""

from pathlib import Path
import ast
import hashlib

COMFY_REV = "0b05cd8a3683cbf0c291b1472bb8b64da41de9ae"
GGUF_REV = "373048b8403a7820620065210a691263d4da0a61"
SP_REV = "a864277f81ee7609972eb64cd1fb086f239d4c99"

SAFE_OLD = """    if destination is None:
        stream_ptr = getattr(stream, "cuda_stream", 0) if stream is not None else 0
        comfy_aimdo.host_buffer.read_file_to_device(file_obj, info.offset, info.size,
                                                    stream_ptr, destination2.data_ptr(),
                                                    destination2.device.index,
                                                    mark_cold=False)
        return True
"""
SAFE_NEW = """    if destination is None:
        # H3_SAFE_FILE_COPY_V1: request caller's standard tensor.copy_ fallback.
        # Prior native SIGSEGV root cause remains unconfirmed.
        import logging
        if not getattr(read_tensor_file_slice_into, "_h3_logged", False):
            logging.warning("[h3_safe_copy] standard tensor.copy_ fallback active")
            read_tensor_file_slice_into._h3_logged = True
        return False
"""

GPU_SMOKE_SOURCE = """import json,sys,tempfile,threading
from pathlib import Path
import torch
import comfy.memory_management as mm
import comfy_aimdo.host_buffer as hb
idx=int(sys.argv[1]);torch.cuda.set_device(idx)
if torch.cuda.device_count()<2:raise RuntimeError("H3 requires two allocated CUDA devices")
expected=torch.arange(256,dtype=torch.uint8).repeat(4096)
def reject(*args,**kwargs):raise AssertionError("Unsafe native file reader reached")
hb.read_file_to_device=reject
with tempfile.TemporaryDirectory() as d:
 p=Path(d)/"mapped.bin";p.write_bytes(expected.numpy().tobytes())
 source=torch.from_file(str(p),shared=False,size=expected.numel(),dtype=torch.uint8)
 with p.open("rb") as f:
  source.untyped_storage()._comfy_tensor_file_slice=mm.TensorFileSlice(f,threading.Lock(),0,expected.numel())
  for _ in range(16):
   dest=torch.empty_like(expected,device="cuda:"+str(idx))
   if mm.read_tensor_file_slice_into(source,dest):raise AssertionError("Expected copy fallback")
   dest.copy_(source,non_blocking=False);torch.cuda.synchronize(idx)
   if not torch.equal(dest.cpu(),expected):raise AssertionError("GPU bytes differ")
print("H3_GPU_COPY_SMOKE_PASS "+json.dumps({"gpu":idx,"repeats":16,"byte_exact":True}),flush=True)
"""

NODE_SOURCE = '''"""Owned saver: persisted native frames + joint audio/video, no overlays."""
from pathlib import Path
import subprocess,wave
import numpy as np
from PIL import Image
import folder_paths
class H3NativeVideoSave:
 @classmethod
 def INPUT_TYPES(cls):return {"required":{"video":("VIDEO",),"filename_prefix":("STRING",{"default":"h3/segment"})}}
 RETURN_TYPES=()
 OUTPUT_NODE=True
 FUNCTION="save"
 CATEGORY="video"
 def save(self,video,filename_prefix):
  if not filename_prefix or any(p in ("",".","..") for p in filename_prefix.split("/")) or "\\\\" in filename_prefix:raise ValueError("Unsafe prefix")
  root=Path(folder_paths.get_output_directory()).resolve();prefix=(root/filename_prefix).resolve()
  if not prefix.is_relative_to(root):raise ValueError("Output escape")
  prefix.parent.mkdir(parents=True,exist_ok=True)
  frames=prefix.with_name(prefix.name+"-frames")
  frames.mkdir(exist_ok=False)
  parts=video.get_components();entries=[]
  for i,img in enumerate(parts.images):
   array=img.float().cpu().numpy()
   if not np.isfinite(array).all():raise ValueError("Nonfinite native frame")
   path=frames/f"{i:06d}.png";Image.fromarray((np.clip(array,0,1)*255).astype(np.uint8)).save(path)
   entries.append({"filename":path.name,"subfolder":str(frames.relative_to(root)),"type":"output"})
  if not entries:raise ValueError("No native frames")
  audio=parts.audio
  if not audio:raise ValueError("Missing native H3 audio")
  samples=audio["waveform"][0].float().cpu().numpy()
  if not np.isfinite(samples).all():raise ValueError("Nonfinite native audio")
  wav=prefix.with_suffix(".wav");pcm=(np.clip(samples,-1,1).T*32767).astype("<i2")
  with wave.open(str(wav),"wb") as f:f.setnchannels(samples.shape[0]);f.setsampwidth(2);f.setframerate(int(audio["sample_rate"]));f.writeframes(pcm.tobytes())
  path=prefix.with_suffix(".mp4")
  if path.exists():raise ValueError("Refuse existing output")
  subprocess.run(["ffmpeg","-y","-v","error","-threads","2","-framerate",str(float(parts.frame_rate)),"-i",str(frames/"%06d.png"),"-i",str(wav),"-c:v","libx264","-crf","14","-preset","medium","-pix_fmt","yuv420p","-c:a","aac","-b:a","192k","-shortest","-movflags","+faststart",str(path)],check=True,timeout=300)
  wav.unlink()
  return {"ui":{"images":entries,"videos":[{"filename":path.name,"subfolder":str(path.parent.relative_to(root)),"type":"output"}]}}
NODE_CLASS_MAPPINGS={"H3NativeVideoSave":H3NativeVideoSave}
'''


def replace_once(source, old, new, label):
    if source.count(old) != 1:
        raise RuntimeError("Pinned H3 patch anchor changed: " + label)
    return source.replace(old, new, 1)


def apply(comfy_root, gguf_root, sp_root):
    """Patch fresh pinned checkout only, compile all candidates before writes."""
    comfy, gguf, sp = Path(comfy_root), Path(gguf_root), Path(sp_root)
    names = {
        "gguf": gguf / "nodes.py",
        "group": sp / "minimax_sp/sp_group.py",
        "forward": sp / "minimax_sp/sp_forward.py",
        "worker": sp / "minimax_sp/sp_worker.py",
        "patches": sp / "minimax_sp/sp_patches.py",
        "model": comfy / "comfy/ldm/minimax/model.py",
        "llama": comfy / "comfy/text_encoders/llama.py",
        "memory": comfy / "comfy/memory_management.py",
    }
    original = {name: path.read_text() for name, path in names.items()}
    updated = original.copy()
    marker = "    def load_patcher(self, clip_paths, clip_type, clip_data):\n"
    updated["gguf"] = replace_once(
        updated["gguf"],
        marker,
        marker + "        if clip_type == comfy.sd.CLIPType.MINIMAX:\n"
        "            clip_data = [{(k[len('model.'):] if k.startswith('model.visual.') else k): v for k, v in sd.items()} for sd in clip_data]\n",
        "GGUF vision prefix",
    )
    updated["group"] = replace_once(
        updated["group"],
        '"force_fp16", "fp16_unet", "fp32_unet", "bf16_unet", "disable_dynamic_vram",',
        '"force_fp32", "force_fp16", "fp16_unet", "fp32_unet", "bf16_unet", "disable_dynamic_vram",',
        "worker precision flags",
    )
    updated["group"] = replace_once(
        updated["group"],
        '"disable_triton_backend", "highvram", "lowvram", "reserve_vram",',
        '"disable_async_offload", "async_offload", "disable_triton_backend", "highvram", "lowvram", "reserve_vram",',
        "worker offload flags",
    )
    spawn = '            logging.info(f"[minimax_sp] spawned worker rank {r} on physical GPU {devices[r]}")'
    watcher = """
            import threading as _h3_threading
            def _h3_watch_worker(proc, rank):
                rc = proc.wait()
                if rc != 0:
                    from pathlib import Path as _h3_Path
                    status = {"rank": rank, "returncode": rc, "pid": proc.pid}
                    _h3_Path(log_dir, f"rank{rank}-failed.json").write_text(json.dumps(status))
                    logging.error("[h3_worker_dead] %s", status)
            _h3_threading.Thread(target=_h3_watch_worker, args=(self.procs[-1], r), daemon=True).start()
"""
    updated["group"] = replace_once(
        updated["group"], spawn, spawn + watcher, "worker death marker"
    )
    updated["forward"] = replace_once(
        updated["forward"],
        "    dist.all_gather_single(gathered, buf, group=ctx.group)",
        '    if not callable(getattr(dist, "all_gather_into_tensor", None)):\n'
        '        raise RuntimeError("Required public gather API missing")\n'
        "    dist.all_gather_into_tensor(gathered, buf.contiguous(), group=ctx.group)",
        "public gather",
    )
    updated["forward"] = replace_once(
        updated["forward"],
        "    for i, block in enumerate(dit.blocks):\n",
        "    for i, block in enumerate(dit.blocks):\n"
        '        logging.info("[h3_diag] rank=%s block=%s prefetch_begin", rank, i)\n',
        "block progress",
    )
    updated["forward"] = replace_once(
        updated["forward"],
        "        h = sp_block(block, h, t_emb, local_segments, rope_for_blocks, ctx, transformer_options)",
        '        logging.info("[h3_diag] rank=%s block=%s compute_begin", rank, i)\n'
        "        h = sp_block(block, h, t_emb, local_segments, rope_for_blocks, ctx, transformer_options)\n"
        '        logging.info("[h3_diag] rank=%s block=%s compute_returned", rank, i)',
        "block execution",
    )
    updated["patches"] = replace_once(
        updated["patches"],
        '                patches = torch.load(stream, map_location="cpu", weights_only=True)',
        "                from comfy.weight_adapter.lora import LoRAAdapter\n"
        "                with torch.serialization.safe_globals([LoRAAdapter]):\n"
        '                    patches = torch.load(stream, map_location="cpu", weights_only=True)',
        "safe LoRA deserialization",
    )
    cleanup = "    finally:\n        initialized = dist.is_initialized()\n"
    diagnostics = """        import sys as _h3_sys
        import traceback as _h3_tb
        import threading as _h3_threading
        _h3_error = _h3_sys.exc_info()[1]
        if _h3_error is not None:
            logging.error("rank %s: original failure before cleanup: %s", a.rank, _h3_error)
            from pathlib import Path as _h3_Path
            _h3_Path(os.environ.get("MINIMAX_SP_LOGDIR", "/tmp"), f"rank{a.rank}-exception.txt").write_text("".join(_h3_tb.format_exception(_h3_error)))
        def _h3_cleanup_deadline():
            logging.error("rank %s: cleanup exceeded 120 seconds", a.rank)
            os._exit(3)
        _h3_timer = _h3_threading.Timer(120, _h3_cleanup_deadline)
        _h3_timer.daemon = True
        _h3_timer.start()
"""
    updated["worker"] = replace_once(
        updated["worker"],
        cleanup,
        "    finally:\n"
        + diagnostics
        + "        initialized = dist.is_initialized()\n",
        "worker failure diagnostics",
    )
    updated["worker"] = replace_once(
        updated["worker"],
        "                dist.destroy_process_group(tensor_pg)\n",
        "                dist.destroy_process_group(tensor_pg)\n"
        '        except Exception:\n            logging.exception("H3 tensor group cleanup failed")\n',
        "worker tensor cleanup",
    )
    updated["worker"] = replace_once(
        updated["worker"],
        "                    dist.destroy_process_group(control_pg)\n",
        "                    dist.destroy_process_group(control_pg)\n"
        '            except Exception:\n                logging.exception("H3 control group cleanup failed")\n',
        "worker control cleanup",
    )
    updated["group"] = replace_once(
        updated["group"],
        "            process.wait()\n",
        "            try:\n                process.wait(timeout=30)\n"
        '            except subprocess.TimeoutExpired:\n                logging.error("H3 worker cleanup timed out pid=%s", process.pid)\n',
        "parent bounded worker cleanup",
    )
    old_mlp = '    def forward(self, x):\n        return comfy.ops.linear_input_act(self.fc2, self.fc1(x), "swiglu")'
    new_mlp = """    def forward(self, x):
        if x.ndim == 2 and x.shape[0] > 256:
            out = torch.empty_like(x)
            for start in range(0, x.shape[0], 256):
                stop = min(start + 256, x.shape[0])
                out[start:stop] = comfy.ops.linear_input_act(self.fc2, self.fc1(x[start:stop]), "swiglu")
            return out
        return comfy.ops.linear_input_act(self.fc2, self.fc1(x), "swiglu")"""
    updated["model"] = replace_once(
        updated["model"], old_mlp, new_mlp, "token-local DiT FFN"
    )
    llama = updated["llama"]
    start = llama.find("class MLP(nn.Module):")
    if start < 0:
        raise RuntimeError("Pinned H3 Qwen MLP class changed")
    split = llama.find("    def forward(self, x, norm=None):", start)
    if split < 0:
        raise RuntimeError("Pinned H3 Qwen forward changed")
    llama = llama[:split] + llama[split:].replace(
        "    def forward(self, x, norm=None):",
        "    def _h3_original_forward(self, x, norm=None):",
        1,
    )
    wrapper = """    def forward(self, x, norm=None):
        if x.ndim >= 3 and x.shape[-2] > 256:
            out = torch.empty_like(x)
            for start in range(0, x.shape[-2], 256):
                end = min(start + 256, x.shape[-2])
                out[..., start:end, :] = self._h3_original_forward(x[..., start:end, :], norm)
            return out
        return self._h3_original_forward(x, norm)

"""
    updated["llama"] = llama[:split] + wrapper + llama[split:]
    updated["memory"] = replace_once(
        updated["memory"], SAFE_OLD, SAFE_NEW, "standard file-copy fallback"
    )
    function = next(
        n
        for n in ast.parse(updated["memory"]).body
        if isinstance(n, ast.FunctionDef) and n.name == "read_tensor_file_slice_into"
    )
    if any(
        isinstance(n, ast.Attribute) and n.attr == "read_file_to_device"
        for n in ast.walk(function)
    ):
        raise RuntimeError("Native direct reader still reachable")
    for name, source in updated.items():
        compile(source, str(names[name]), "exec")
    compile(NODE_SOURCE, "h3-native-save.py", "exec")
    compile(GPU_SMOKE_SOURCE, "h3-gpu-smoke.py", "exec")
    saver = comfy / "custom_nodes/h3_native_save.py"
    smoke = comfy / "h3_gpu_copy_smoke.py"
    if saver.exists() or smoke.exists():
        raise RuntimeError(
            "H3 compatibility files already exist; require a fresh workspace"
        )
    for name, source in updated.items():
        names[name].write_text(source)
    saver.write_text(NODE_SOURCE)
    smoke.write_text(GPU_SMOKE_SOURCE)
    return {
        "profile": "minimax-h3-t4-v1",
        "native_root_cause_confirmed": False,
        "files": [
            {
                "role": name,
                "before_sha256": hashlib.sha256(original[name].encode()).hexdigest(),
                "after_sha256": hashlib.sha256(source.encode()).hexdigest(),
            }
            for name, source in updated.items()
        ],
    }
