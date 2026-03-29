#!/usr/bin/env python3
"""范式合规验证 - 主入口脚本

本脚本是项目开发范式的硬性强制工具。
可被Git hooks、Claude Code hooks、或人工直接调用。

用法:
    python scripts/validate_paradigm.py --all              # 全量检查
    python scripts/validate_paradigm.py --spec <path>      # 校验Feature Spec格式
    python scripts/validate_paradigm.py --sprint <path>    # 校验Sprint Report完整性
    python scripts/validate_paradigm.py --pre-commit       # 提交前检查
    python scripts/validate_paradigm.py --deps             # 依赖一致性检查
    python scripts/validate_paradigm.py --claude-md        # CLAUDE.md状态检查
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

# 项目根目录
ROOT = Path(__file__).resolve().parent.parent

# 颜色输出
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BOLD = "\033[1m"
RESET = "\033[0m"


def ok(msg: str) -> None:
    print(f"  {GREEN}[通过]{RESET} {msg}")


def warn(msg: str) -> None:
    print(f"  {YELLOW}[警告]{RESET} {msg}")


def fail(msg: str) -> None:
    print(f"  {RED}[失败]{RESET} {msg}")


def header(title: str) -> None:
    print(f"\n{BOLD}=== {title} ==={RESET}")


# ============================================================
# Feature Spec 格式校验
# ============================================================

SPEC_REQUIRED_SECTIONS = [
    "User Story",
    "Acceptance Criteria",
    "Data Flow",
    "API Contract",
    "Dependencies",
    "Non-functional Requirements",
    "Skills Evaluation",
]


def validate_spec(spec_path: str) -> bool:
    """校验Feature Spec是否包含所有必需章节。"""
    header(f"校验Feature Spec: {spec_path}")

    path = Path(spec_path)
    if not path.exists():
        fail(f"文件不存在: {spec_path}")
        return False

    content = path.read_text(encoding="utf-8")
    all_pass = True

    for section in SPEC_REQUIRED_SECTIONS:
        # 匹配 ## 或 ### 开头的章节标题
        pattern = rf"^##\s+.*{re.escape(section)}"
        if re.search(pattern, content, re.MULTILINE | re.IGNORECASE):
            ok(f"包含章节: {section}")
        else:
            fail(f"缺少必需章节: {section}")
            all_pass = False

    # 检查验收标准是否有可勾选项
    ac_pattern = r"- \[[ x]\]"
    if re.search(ac_pattern, content):
        ok("验收标准包含可测试的条件列表")
    else:
        fail("验收标准缺少可勾选项 (格式: - [ ] AC-N: 描述)")
        all_pass = False

    return all_pass


# ============================================================
# Sprint Report 完整性校验
# ============================================================

SPRINT_REQUIRED_FIELDS = [
    "Feature Spec",
    "Files Changed",
    "New Dependencies",
    "Test Coverage",
    "Self-Check Results",
    "Known Limitations",
    "Integrated Skills",
]

# 中文等效字段名（兼容中文Sprint Report）
SPRINT_REQUIRED_FIELDS_ZH = [
    "功能规格",
    "新增/修改文件",
    "新增依赖",
    "测试覆盖",
    "自检清单",
    "已知限制",
    "集成的外部skills",
]


def validate_sprint_report(report_path: str) -> bool:
    """校验Sprint Report是否包含所有必需字段。"""
    header(f"校验Sprint Report: {report_path}")

    path = Path(report_path)
    if not path.exists():
        fail(f"文件不存在: {report_path}")
        return False

    content = path.read_text(encoding="utf-8")
    all_pass = True

    for field_en, field_zh in zip(SPRINT_REQUIRED_FIELDS, SPRINT_REQUIRED_FIELDS_ZH):
        if field_en.lower() in content.lower() or field_zh in content:
            ok(f"包含字段: {field_en} / {field_zh}")
        else:
            fail(f"缺少必需字段: {field_en} ({field_zh})")
            all_pass = False

    return all_pass


# ============================================================
# 依赖一致性检查
# ============================================================


def validate_deps() -> bool:
    """检查Python依赖是否一致。"""
    header("依赖一致性检查")

    req_path = ROOT / "requirements.txt"
    pyproject_path = ROOT / "pyproject.toml"

    all_pass = True

    # 检查requirements.txt是否存在
    if not req_path.exists():
        if any((ROOT / "src").rglob("*.py")):
            fail("存在Python源码但缺少requirements.txt")
            all_pass = False
        else:
            warn("requirements.txt不存在（项目尚无Python源码，可忽略）")
        return all_pass

    # 检查requirements.txt中的包是否有版本锁定
    lines = req_path.read_text(encoding="utf-8").strip().split("\n")
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        if "==" not in line:
            warn(f"依赖未锁定精确版本: {line}（应使用 == 锁定）")

    # 检查pyproject.toml是否存在
    if not pyproject_path.exists():
        if req_path.exists() and req_path.stat().st_size > 0:
            warn("存在requirements.txt但缺少pyproject.toml")

    # 检查import是否都在requirements.txt中（简单启发式检查）
    if (ROOT / "src").exists():
        _check_import_coverage(req_path)

    ok("依赖检查完成")
    return all_pass


def _check_import_coverage(req_path: Path) -> None:
    """启发式检查：源码中的import是否都在requirements.txt中有对应的包。"""
    req_text = req_path.read_text(encoding="utf-8").lower()

    # 标准库模块（部分常见的，不需要安装）
    stdlib = {
        "os", "sys", "re", "json", "datetime", "pathlib", "typing",
        "abc", "dataclasses", "enum", "collections", "functools",
        "asyncio", "logging", "hashlib", "math", "random", "time",
        "unittest", "io", "copy", "itertools", "contextlib",
        "subprocess", "shutil", "tempfile", "textwrap", "argparse",
        "configparser", "tomllib", "sqlite3", "urllib",
    }

    third_party_imports = set()
    for py_file in (ROOT / "src").rglob("*.py"):
        for line in py_file.read_text(encoding="utf-8", errors="ignore").split("\n"):
            match = re.match(r"^(?:from|import)\s+([\w]+)", line)
            if match:
                module = match.group(1).lower()
                if module not in stdlib and module != "src":
                    third_party_imports.add(module)

    for module in sorted(third_party_imports):
        # 包名和import名可能不同（如 Pillow -> PIL），只做粗略检查
        if module not in req_text:
            warn(f"源码中import了 '{module}'，但requirements.txt中未找到对应包（可能包名不同）")


# ============================================================
# CLAUDE.md 状态检查
# ============================================================


def validate_claude_md() -> bool:
    """检查CLAUDE.md是否存在且包含关键内容。"""
    header("CLAUDE.md 状态检查")

    claude_path = ROOT / "CLAUDE.md"
    if not claude_path.exists():
        fail("CLAUDE.md不存在！这是项目根权威文档，必须存在。")
        return False

    content = claude_path.read_text(encoding="utf-8")
    all_pass = True

    # 检查范式权威声明
    if "FIRST-CLASS" in content or "一等公民" in content:
        ok("包含范式权威声明")
    else:
        fail("缺少范式权威声明（FIRST-CLASS / 一等公民）")
        all_pass = False

    # 检查范式文档引用
    paradigm_refs = [
        "docs/paradigm/agent-roles.md",
        "docs/paradigm/sprint-workflow.md",
        "docs/paradigm/quality-gates.md",
    ]
    for ref in paradigm_refs:
        if ref in content:
            ok(f"引用范式文档: {ref}")
        else:
            fail(f"缺少范式文档引用: {ref}")
            all_pass = False

    # 检查Module Checklist存在
    if "Module" in content and ("Checklist" in content or "清单" in content):
        ok("包含模块开发清单")
    else:
        fail("缺少模块开发清单（Module Checklist）")
        all_pass = False

    # 检查范式文档文件是否都存在
    for ref in paradigm_refs:
        if not (ROOT / ref).exists():
            fail(f"范式文档文件缺失: {ref}")
            all_pass = False
        else:
            ok(f"范式文档文件存在: {ref}")

    return all_pass


# ============================================================
# 提交前检查（Pre-commit）
# ============================================================


def validate_pre_commit() -> bool:
    """提交前的综合检查。"""
    header("提交前检查")

    all_pass = True

    # 1. 检查是否在main分支直接提交
    try:
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=ROOT, text=True
        ).strip()
    except subprocess.CalledProcessError:
        warn("无法获取当前分支名")
        branch = "unknown"

    if branch == "main":
        # 检查是否是merge commit
        try:
            merge_head = (ROOT / ".git" / "MERGE_HEAD").exists()
        except Exception:
            merge_head = False

        if not merge_head:
            warn("正在main分支直接提交。范式要求通过feature分支开发后合并。")
            warn("如果这是项目初始化阶段的提交，可以忽略此警告。")
    else:
        ok(f"当前分支: {branch}（非main直接提交）")

    # 2. 检查暂存文件中是否有敏感信息
    try:
        staged = subprocess.check_output(
            ["git", "diff", "--cached", "--name-only"],
            cwd=ROOT, text=True
        ).strip().split("\n")
    except subprocess.CalledProcessError:
        staged = []

    for f in staged:
        if not f:
            continue
        if f in (".env", ".env.local"):
            fail(f"禁止提交敏感文件: {f}")
            all_pass = False
        elif f.endswith((".key", ".pem", ".p12")):
            fail(f"禁止提交密钥文件: {f}")
            all_pass = False

    # 3. 检查暂存的代码中是否有硬编码的API Key模式
    try:
        diff = subprocess.check_output(
            ["git", "diff", "--cached", "-U0"],
            cwd=ROOT, text=True
        )
    except subprocess.CalledProcessError:
        diff = ""

    # 常见API Key模式
    key_patterns = [
        r'sk-[a-zA-Z0-9]{20,}',           # OpenAI
        r'sk-ant-[a-zA-Z0-9]{20,}',       # Anthropic
        r'AIza[a-zA-Z0-9_-]{35}',          # Google
        r'ghp_[a-zA-Z0-9]{36}',            # GitHub
    ]
    for pattern in key_patterns:
        matches = re.findall(pattern, diff)
        if matches:
            fail(f"检测到疑似硬编码API Key: {pattern[:20]}...")
            all_pass = False

    if all_pass:
        ok("未发现敏感信息泄露")

    # 4. 检查是否有Python源码修改但未更新测试
    src_changed = any(f.startswith("src/") and f.endswith(".py") for f in staged if f)
    test_changed = any(f.startswith("tests/") for f in staged if f)
    if src_changed and not test_changed:
        warn("修改了src/下的代码但未更新tests/下的测试文件。请确认是否需要补充测试。")

    # 5. 运行lint（如果ruff可用且有Python文件）
    if src_changed:
        _run_lint()

    # 6. CLAUDE.md完整性
    claude_ok = validate_claude_md()
    if not claude_ok:
        all_pass = False

    return all_pass


def _run_lint() -> None:
    """运行ruff lint检查。"""
    try:
        result = subprocess.run(
            ["ruff", "check", "src/"],
            cwd=ROOT, capture_output=True, text=True
        )
        if result.returncode == 0:
            ok("ruff lint检查通过")
        else:
            fail("ruff lint检查未通过:")
            for line in result.stdout.strip().split("\n")[:10]:
                print(f"    {line}")
            if result.stdout.count("\n") > 10:
                print(f"    ... 还有更多错误")
    except FileNotFoundError:
        warn("ruff未安装，跳过lint检查（建议安装: pip install ruff）")


# ============================================================
# 提交消息格式校验
# ============================================================

COMMIT_MSG_PATTERN = re.compile(
    r"^(feat|fix|test|docs|refactor|chore)(\([a-z0-9_-]+\))?: .{3,}$",
    re.MULTILINE
)


def validate_commit_msg(msg_file: str) -> bool:
    """校验提交消息是否符合规范格式。"""
    header("提交消息格式校验")

    path = Path(msg_file)
    if not path.exists():
        fail(f"提交消息文件不存在: {msg_file}")
        return False

    msg = path.read_text(encoding="utf-8").strip()

    # 跳过merge commit
    if msg.startswith("Merge"):
        ok("Merge commit，跳过格式检查")
        return True

    first_line = msg.split("\n")[0]

    if COMMIT_MSG_PATTERN.match(first_line):
        ok(f"提交消息格式正确: {first_line}")
        return True
    else:
        fail(f"提交消息格式不符合规范: {first_line}")
        print(f"    要求格式: <type>(<module>): <description>")
        print(f"    type可选: feat, fix, test, docs, refactor, chore")
        print(f"    示例: feat(data): 添加AkShare数据源适配器")
        return False


# ============================================================
# 全量检查
# ============================================================


def validate_all() -> bool:
    """运行所有验证。"""
    results = []

    results.append(("CLAUDE.md状态", validate_claude_md()))
    results.append(("依赖一致性", validate_deps()))

    # 校验所有Feature Spec
    specs_dir = ROOT / "specs"
    if specs_dir.exists():
        for spec_file in specs_dir.rglob("*.md"):
            if ".sprint-" not in spec_file.name and ".qa-" not in spec_file.name:
                results.append(
                    (f"Spec: {spec_file.name}", validate_spec(str(spec_file)))
                )

    # 汇总
    header("验证汇总")
    all_pass = True
    for name, passed in results:
        if passed:
            ok(name)
        else:
            fail(name)
            all_pass = False

    if all_pass:
        print(f"\n{GREEN}{BOLD}全部检查通过{RESET}")
    else:
        print(f"\n{RED}{BOLD}存在未通过的检查项，请修复后重试{RESET}")

    return all_pass


# ============================================================
# 主入口
# ============================================================


def main() -> None:
    parser = argparse.ArgumentParser(description="范式合规验证工具")
    parser.add_argument("--all", action="store_true", help="运行全量检查")
    parser.add_argument("--spec", type=str, help="校验Feature Spec格式")
    parser.add_argument("--sprint", type=str, help="校验Sprint Report完整性")
    parser.add_argument("--pre-commit", action="store_true", help="提交前检查")
    parser.add_argument("--commit-msg", type=str, help="校验提交消息格式")
    parser.add_argument("--deps", action="store_true", help="依赖一致性检查")
    parser.add_argument("--claude-md", action="store_true", help="CLAUDE.md状态检查")

    args = parser.parse_args()

    if not any(vars(args).values()):
        parser.print_help()
        sys.exit(0)

    passed = True

    if args.all:
        passed = validate_all()
    if args.spec:
        passed = validate_spec(args.spec) and passed
    if args.sprint:
        passed = validate_sprint_report(args.sprint) and passed
    if args.pre_commit:
        passed = validate_pre_commit() and passed
    if args.commit_msg:
        passed = validate_commit_msg(args.commit_msg) and passed
    if args.deps:
        passed = validate_deps() and passed
    if args.claude_md:
        passed = validate_claude_md() and passed

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
