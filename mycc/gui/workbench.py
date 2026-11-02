"""Pure compiler workbench model, independent of boards and process runners."""

from dataclasses import dataclass, field
import contextlib
import io
import json
from pathlib import Path
import subprocess
from .. import core

DUMP_KEYS = ("tokens", "ast", "ir", "isa", "isa_whitelist", "lowering_report")
DUMP_FLAGS = {
    "tokens": "--dump-tokens",
    "ast": "--dump-ast",
    "ir": "--dump-ir",
    "isa": "--dump-isa",
    "isa_whitelist": "--dump-isa-whitelist",
    "lowering_report": "--dump-lowering-report",
}
DEFAULT_DUMPS = {
    "tokens": True,
    "ast": True,
    "ir": True,
    "isa": False,
    "isa_whitelist": False,
    "lowering_report": True,
}
TARGETS = ("generic", "cpu21", "logisim")
THEME_NAMES = ("system", "light", "dark", "contrast")


@dataclass
class WorkbenchState:
    text: str = (
        "int square(int x) { return x * x; }\n\nint main(void) {\n    return square(7);\n}\n"
    )
    path: str = "<untitled>"
    baseline: str = "PF-01"
    enable: list = field(default_factory=list)
    disable: list = field(default_factory=list)
    target: str = "generic"
    output: str = ""
    write_output: bool = False
    rars: bool = False
    logisim: bool = False
    stack_top: str = ""
    isa_file: str = ""
    dumps: dict = field(default_factory=lambda: dict(DEFAULT_DUMPS))
    stats: bool = False
    theme: str = "system"
    result: object = None
    last_asm: str = ""
    stale: bool = False
    legacy: dict = field(default_factory=dict)


@dataclass(frozen=True)
class CompileRequest:
    src: core.SourceFile
    profile: core.ISAProfile
    options: core.CompileOptions


@dataclass(frozen=True)
class UiModel:
    asm_text: str
    diag_rows: list
    lowering_text: str
    status_line: str
    stale_flags: bool


def default_settings():
    return {
        "baseline": "PF-01",
        "enable": [],
        "disable": [],
        "legacy": {},
        "target": "generic",
        "output": "",
        "write_output": False,
        "rars": False,
        "logisim": False,
        "stack_top": "",
        "isa_file": "",
        "dumps": dict(DEFAULT_DUMPS),
        "stats": False,
        "theme": "system",
    }


def state_from_settings(settings):
    """Build a workbench state from the persisted settings dictionary."""
    state = WorkbenchState()
    for key in ("baseline", "target", "output", "stack_top", "isa_file", "theme"):
        setattr(state, key, settings[key])
    for key in ("write_output", "rars", "logisim", "stats"):
        setattr(state, key, bool(settings[key]))
    state.enable = list(settings["enable"])
    state.disable = list(settings["disable"])
    state.legacy = dict(settings["legacy"])
    state.dumps = {key: bool(settings["dumps"][key]) for key in DUMP_KEYS}
    return state


def _profile(state):
    """Load the profile selected by the workbench, including an ISA file."""
    data = None
    if state.isa_file:
        try:
            data = json.loads(Path(state.isa_file).read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise core.ProfileError(f"cannot read ISA profile: {exc}") from exc
    return core.load_profile(state.baseline, state.enable, state.disable, data)


def profile_for_state(state):
    return _profile(state)


def build_request(state):
    profile = profile_for_state(state)
    options = core.CompileOptions()
    if state.target != "generic":
        from adapters import check_target, compile_options

        check_target(profile, state.target)
        options = compile_options(state.target)
    return CompileRequest(core.SourceFile(state.text, state.path), profile, options)


def stack_value(state):
    text = str(state.stack_top).strip()
    if not text:
        return None
    try:
        value = int(text, 0)
    except (TypeError, ValueError) as exc:
        raise ValueError("栈顶必须是 32 位整数（支持 0x 前缀）") from exc
    if not 0 <= value <= 0xFFFFFFFF:
        raise ValueError("栈顶必须是 32 位地址")
    return value


def output_name(state):
    """Default artifact name when the output field names a directory."""
    stem = Path(state.path).stem if state.path not in ("", "<untitled>") else "main"
    return f'{stem}{".asm" if state.target == "logisim" else ".s"}'


def output_file(state):
    """Resolve the output field to a concrete file path.

    The GUI accepts either a file (`.s`/`.asm`) or a directory. A directory can
    be selected with the folder picker, typed with a trailing separator, or typed
    as an existing directory. A suffix-less new path is treated as a directory so
    manual "build/foo" input does not silently create a file called `foo`.
    """
    raw = str(state.output).strip()
    if not raw:
        return None
    path = Path(raw)
    if path.exists() and path.is_dir():
        return path / output_name(state)
    if raw.endswith(("/", "\\")):
        return path / output_name(state)
    if path.exists() and path.is_file():
        return path
    if not path.suffix:
        return path / output_name(state)
    return path


def _write(path, text):
    path = Path(path)
    if path.exists() and path.is_dir():
        raise IsADirectoryError(f"输出路径是目录: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def artifacts(state, request, result):
    """Write the same artifacts as the equivalent CLI switches.

    Returns a list of paths. Raises OSError/ValueError/ProfileError on failure;
    the caller turns those into a status message instead of losing the successful
    in-memory result.
    """
    if not state.write_output or not state.output:
        return []
    out = output_file(state)
    if out is None:
        return []
    paths = []
    if state.target == "logisim":
        from ..rars import images

        text, rom, ram = images(
            result.asm, profile=request.profile, stack_top=stack_value(state)
        )
        _write(out, text)
        paths.append(str(out))
        rom_path = out.with_suffix(".rom.hex")
        _write(
            rom_path,
            "v2.0 raw\n" + "".join(f"{word & 0xffffffff:08x}\n" for word in rom),
        )
        paths.append(str(rom_path))
        if ram:
            ram_path = out.with_suffix(".ram.hex")
            _write(
                ram_path,
                "v2.0 raw\n" + "".join(f"{word & 0xffffffff:08x}\n" for word in ram),
            )
            paths.append(str(ram_path))
    elif state.rars:
        from ..rars import convert

        text = convert(
            result.asm, profile=request.profile, stack_top=stack_value(state)
        )
        _write(out, text)
        paths.append(str(out))
    else:
        _write(out, result.asm)
        paths.append(str(out))
    return paths


def command_text(state):
    """The exact CLI equivalent of the current build settings (for copying)."""
    args = [
        "python",
        "-m",
        "mycc",
        state.path if state.path != "<untitled>" else "<source.c>",
    ]
    out = output_file(state)
    if out is not None:
        args += ["-o", str(out)]
    if state.target != "generic":
        args += ["--target", state.target]
    if state.rars:
        args.append("--rars")
    if state.logisim:
        args.append("--logisim")
    if str(state.stack_top).strip():
        args += ["--stack-top", str(state.stack_top).strip()]
    if state.isa_file:
        args += ["--isa-file", state.isa_file]
    args += ["--profile", state.baseline]
    for name in state.enable:
        args += ["--enable", name]
    disable = list(state.disable)
    for flag, group in (("--no-lui", "lui"), ("--no-vshift", "vshift")):
        if group in disable:
            args.append(flag)
            disable.remove(group)
    for name in disable:
        args += ["--disable", name]
    for key in DUMP_KEYS:
        if state.dumps.get(key):
            args.append(DUMP_FLAGS[key])
    if state.stats:
        args.append("--stats")
    return subprocess.list2cmdline(args)


def normalize_capabilities(baseline, enable=(), disable=()):
    """Reduce enable/disable to the difference from the selected preset.

    A checkbox for a group the preset never contained is not a user decision, so
    recording it in `disable` makes the setting ambiguous: it persists across
    sessions and then removes capabilities the preset does provide. Keeping only
    real differences means PF-01 always means 26 instructions until the user
    explicitly turns something off.

    Older settings (and `--enable`/`--disable` from the CLI) may contain a single
    instruction rather than a group; treat it as a one-instruction set instead of
    failing with KeyError.
    """
    base = core.load_profile(baseline).instructions

    def group(name):
        return core.GROUPS.get(name, {name})

    keep_enable = [name for name in enable if not group(name) <= base]
    keep_disable = [name for name in disable if group(name) <= base]
    return keep_enable, keep_disable


def capability_snapshot(state):
    """Instruction set implied by `state`, without any feasibility check.

    The custom-instruction dialog must stay reachable when the merged profile is
    invalid: unchecking an MV-ISA instruction, a stale ISA file, or a hand-edited
    settings file all make `load_profile` raise, and the dialog used to give up
    with a warning, leaving no way back from the GUI.  This returns the best
    editable approximation plus a note describing what had to be ignored.
    """
    note = ""
    try:
        base = set(core.load_profile(state.baseline).instructions)
    except core.ProfileError:
        base = set(core.load_profile("PF-01").instructions)
        note = f"未知 profile {state.baseline}，暂按 PF-01 显示"
    if state.isa_file:
        try:
            data = json.loads(Path(state.isa_file).read_text(encoding="utf-8-sig"))
            listed = data.get("instructions") if isinstance(data, dict) else None
            if (
                isinstance(listed, list)
                and listed
                and all(isinstance(name, str) and name in core.ALL for name in listed)
            ):
                base = set(listed)
            else:
                note = (
                    f"ISA 文件内容无效（{state.isa_file}），暂按 {state.baseline} 显示"
                )
        except (OSError, UnicodeError, ValueError):
            note = f"ISA 文件无法读取（{state.isa_file}），暂按 {state.baseline} 显示"
    enabled, disabled = set(), set()
    for name in state.enable:
        try:
            enabled |= core.expand([name])
        except core.ProfileError:
            note = note or f"已忽略无法识别的启用项：{name}"
    for name in state.disable:
        try:
            disabled |= core.expand([name])
        except core.ProfileError:
            note = note or f"已忽略无法识别的禁用项：{name}"
    return frozenset((base | enabled) - disabled), note


def apply_result(state, res):
    state.result = res
    if res.success:
        state.last_asm = res.asm
    state.stale = not res.success
    status = (
        "已取消"
        if res.cancelled
        else ("编译成功 · GNU 汇编" if res.success else "编译失败 · 汇编为上次成功结果")
    )
    status += (
        f" · {sum(res.stages_ms.values()):.1f} ms · {len(res.asm.splitlines())} 行"
    )
    return UiModel(
        state.last_asm,
        sorted(res.diagnostics, key=lambda d: (d.line, d.col)),
        core.dump_lowering_report(res),
        status,
        state.stale,
    )


def export_asm_diag_lowering(state):
    res = state.result
    if res is None:
        return state.last_asm, "", ""
    diag = "".join(
        core.format_with_caret(d, res.source or core.SourceFile(state.text, state.path))
        for d in res.diagnostics
    )
    md = "| # | Operation | 位置 | Selected lowering | Rejected | Δ指令 |\n|---|---|---|---|---|---|\n"
    md += "".join(
        f'| {i} | {r.op} | {r.location} | {r.reason} | {", ".join(r.rejected)} | {r.delta:+d} |\n'
        for i, r in enumerate(res.lowering)
    )
    return state.last_asm, diag, md


def source_offset(text, line, col):
    lines = text.splitlines(keepends=True)
    if not lines:
        return 0
    index = max(0, min(line - 1, len(lines) - 1))
    return sum(len(x) for x in lines[:index]) + min(
        max(0, col - 1), len(lines[index].rstrip("\r\n"))
    )


def settings_path():
    return Path.home() / ".config" / "mycc" / "gui.json"


def load_settings(path=None):
    try:
        data = json.loads((path or settings_path()).read_text(encoding="utf-8"))
        allowed = {
            "schema_version",
            "baseline",
            "enable",
            "disable",
            "legacy",
            "board",
            "target",
            "output",
            "write_output",
            "rars",
            "logisim",
            "stack_top",
            "isa_file",
            "dumps",
            "stats",
            "theme",
        }
        if not isinstance(data, dict) or set(data) - allowed:
            raise ValueError("unknown settings fields")
        if data.get("schema_version", 2) != 2:
            raise ValueError("unsupported settings version")
        settings = default_settings()
        for key in ("baseline", "target", "output", "stack_top", "isa_file", "theme"):
            if key in data:
                if not isinstance(data[key], str):
                    raise ValueError(f"{key} must be a string")
                settings[key] = data[key]
        if settings["target"] not in TARGETS or settings["theme"] not in THEME_NAMES:
            raise ValueError("invalid target or theme")
        for key in ("write_output", "rars", "logisim", "stats"):
            if key in data:
                if not isinstance(data[key], bool):
                    raise ValueError(f"{key} must be a boolean")
                settings[key] = data[key]
        for key in ("enable", "disable"):
            if key in data:
                if not isinstance(data[key], list) or not all(
                    isinstance(x, str) for x in data[key]
                ):
                    raise ValueError(f"{key} must be a string array")
                settings[key] = list(data[key])
        if "dumps" in data:
            if not isinstance(data["dumps"], dict) or set(data["dumps"]) - set(
                DUMP_KEYS
            ):
                raise ValueError("invalid dumps")
            for key, value in data["dumps"].items():
                if not isinstance(value, bool):
                    raise ValueError("dumps values must be boolean")
                settings["dumps"][key] = value
        legacy = data.get("legacy", {})
        if not isinstance(legacy, dict):
            raise ValueError("legacy must be an object")
        message = ""
        if "board" in data:
            legacy = {**legacy, "board": data["board"]}
            message = "旧板卡地址设置已保存在 legacy 中；当前工作台仅编译汇编"
        settings["legacy"] = legacy
        core.load_profile(settings["baseline"], settings["enable"], settings["disable"])
        return settings, message
    except FileNotFoundError:
        return default_settings(), ""
    except (OSError, ValueError, KeyError, TypeError, core.ProfileError):
        return default_settings(), "设置损坏，已恢复编译器默认值"


def save_settings(state, path=None):
    try:
        target = path or settings_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "schema_version": 2,
            "baseline": state.baseline,
            "enable": state.enable,
            "disable": state.disable,
            "legacy": state.legacy,
            "target": state.target,
            "output": state.output,
            "write_output": state.write_output,
            "rars": state.rars,
            "logisim": state.logisim,
            "stack_top": state.stack_top,
            "isa_file": state.isa_file,
            "dumps": dict(state.dumps),
            "stats": state.stats,
            "theme": state.theme,
        }
        tmp = target.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(target)
        return ""
    except OSError as exc:
        try:
            tmp.unlink(missing_ok=True)
        except (NameError, OSError):
            pass
        return f"无法保存设置: {exc}"


def doctor_text():
    from ..cli import doctor

    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        doctor()
    return buffer.getvalue()


def isa_text(state, kind="isa"):
    profile = _profile(state)
    if kind == "whitelist":
        return core.dump_isa_whitelist(profile)
    return core.dump_isa(profile)
