#!/usr/bin/env python3
"""yotta-publish-guard 测试：校验三档模式 / pack / versions / names / publish 闸门与渠道。"""
import argparse
import contextlib
import io
import re
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
CLI = HERE / "yotta_publish_guard.py"
sys.path.insert(0, str(HERE))
import yotta_publish_guard as pg  # noqa: E402

README_EN = """<p><b>Language</b>: English · <a href="./README.zh-CN.md">中文</a></p>
# yotta-x

## Installation

npx -y @yottameta/yotta-x --agent codex
git clone https://github.com/YottaMeta/yotta-x.git dir/yotta-x
Download ZIP
bash install.sh --agent codex
"""

README_ZH = """<p><b>Language</b>: <a href="./README.md">English</a> · 中文</p>
# yotta-x

## 安装

npx -y @yottameta/yotta-x --agent codex
git clone https://github.com/YottaMeta/yotta-x.git dir/yotta-x
下载压缩包
bash install.sh --agent codex
"""

SKILL_FULL = """---
name: yotta-x
description: 测试技能。触发：用户说 元X。边界：Do NOT trigger 不做什么。
version: 0.1.0
license: MIT
metadata:
  zh_name: 元X
---

# 元X（yotta-x）

正文。范围：自有环境。授权：用户拥有或获授权。法律：合规。
"""

PKG = {
    "name": "@yottameta/yotta-x",
    "version": "0.1.0",
    "description": "测试技能。",
    "license": "MIT",
    "files": ["SKILL.md", "LICENSE", "README.md", "README.zh-CN.md"],
}


def write(d: Path, rel: str, text: str):
    p = d / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def make_complete(d: Path):
    write(d, "SKILL.md", SKILL_FULL)
    write(d, "LICENSE", "MIT License\nCopyright (c) 2026 YottaMeta\n")
    write(d, "README.md", README_EN)
    write(d, "README.zh-CN.md", README_ZH)
    write(d, "CHANGELOG.md", "## v0.1.0 (2026-08-29)\n\n初始发布。\n")
    write(d, "NOTICE", "# NOTICE\nYottaMeta 品牌声明。\n")
    write(d, "package.json", json.dumps(PKG, ensure_ascii=False, indent=2))


def make_self_use(d: Path):
    write(d, "SKILL.md", SKILL_FULL)
    write(d, "references", "# references\n按需读取。\n")


def make_github(d: Path):
    write(d, "SKILL.md", SKILL_FULL)
    write(d, "LICENSE", "MIT License\n")
    write(d, "README.md", README_EN)


def run_cli(*argv):
    r = subprocess.run([sys.executable, str(CLI)] + list(argv), capture_output=True)
    return r.returncode, r.stdout.decode("utf-8", errors="replace"), \
        r.stderr.decode("utf-8", errors="replace")


class TmpDir(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.mkdtemp(prefix="pg-test-")
        self.addCleanup(shutil.rmtree, self._td, ignore_errors=True)
        self._d = Path(self._td) / "yotta-x"
        self._d.mkdir()

    @property
    def d(self) -> Path:
        return self._d


class TestBasics(unittest.TestCase):
    def test_version(self):
        code, out, _ = run_cli("--version")
        self.assertEqual(code, 0)
        self.assertIn("yotta-publish-guard", out)


class TestValidate(TmpDir):
    def test_full_pass(self):
        make_complete(self.d)
        errors, warns = pg.validate_dir(self.d, mode="full")
        self.assertEqual(errors, [], "errors: %s" % errors)

    def test_full_missing_skill(self):
        errors, _ = pg.validate_dir(self.d, mode="full")
        self.assertTrue(any("SKILL.md" in e for e in errors))

    def test_full_requires_bilingual(self):
        make_github(self.d)
        errors, _ = pg.validate_dir(self.d, mode="full")
        self.assertTrue(any("README.zh-CN.md" in e for e in errors))
        self.assertTrue(any("package.json" in e for e in errors))

    def test_self_use_pass(self):
        make_self_use(self.d)
        errors, _ = pg.validate_dir(self.d, mode="self")
        self.assertEqual(errors, [])

    def test_self_use_full_blocked(self):
        make_self_use(self.d)
        errors, _ = pg.validate_dir(self.d, mode="full")
        self.assertTrue(errors)

    def test_github_mode_pass(self):
        make_github(self.d)
        errors, _ = pg.validate_dir(self.d, mode="github")
        self.assertEqual(errors, [], "errors: %s" % errors)

    def test_github_mode_full_blocked(self):
        make_github(self.d)
        errors, _ = pg.validate_dir(self.d, mode="full")
        self.assertTrue(any("package.json" in e for e in errors))

    def test_voice_blacklist(self):
        make_self_use(self.d)
        write(self.d, "README.md", "# x\n咱们自己用\n")
        errors, _ = pg.validate_dir(self.d, mode="github")
        self.assertTrue(any("咱们" in e for e in errors))

    def test_placeholder_detected(self):
        write(self.d, "SKILL.md",
              "---\nname: yotta-x\ndescription: d\nversion: 0.1.0\n"
              "license: MIT\n---\n{{skill_name}}\n")
        errors, _ = pg.validate_dir(self.d, mode="self")
        self.assertTrue(any("占位符" in e for e in errors))

    def test_version_mismatch(self):
        make_complete(self.d)
        write(self.d, "CHANGELOG.md", "## v0.2.0\n\nx\n")
        errors, _ = pg.validate_dir(self.d, mode="full")
        self.assertTrue(any("版本不一致" in e for e in errors))


class TestVersions(TmpDir):
    def test_aligned(self):
        make_complete(self.d)
        code = pg.cmd_versions(argparse.Namespace(dir=str(self.d)))
        self.assertEqual(code, 0)

    def test_mismatch(self):
        make_complete(self.d)
        write(self.d, "CHANGELOG.md", "## v9.9.9\n\nx\n")
        code = pg.cmd_versions(argparse.Namespace(dir=str(self.d)))
        self.assertEqual(code, 2)


class TestPack(TmpDir):
    def _fake_npm(self, files):
        def fake(cmd, cwd=None, env=None, timeout=120):
            if "npm" in cmd[0].lower():  # shutil.which 返回全路径（如 ...npm.CMD）
                payload = {"@yottameta/yotta-x": {
                    "files": [{"path": p, "size": 1} for p in files]}}
                return 0, json.dumps(payload), ""
            return 127, "", "missing"
        return fake

    def test_pack_pass(self):
        make_complete(self.d)
        orig = pg.run_cmd
        pg.run_cmd = self._fake_npm(
            ["SKILL.md", "LICENSE", "README.md", "README.zh-CN.md",
             "CHANGELOG.md", "NOTICE"])
        try:
            code = pg.cmd_pack(argparse.Namespace(dir=str(self.d)))
        finally:
            pg.run_cmd = orig
        self.assertEqual(code, 0)

    def test_pack_pyc_blocked(self):
        make_complete(self.d)
        orig = pg.run_cmd
        pg.run_cmd = self._fake_npm(
            ["SKILL.md", "scripts/x.pyc"])
        try:
            code = pg.cmd_pack(argparse.Namespace(dir=str(self.d)))
        finally:
            pg.run_cmd = orig
        self.assertEqual(code, 2)

    def test_pack_missing_key(self):
        make_complete(self.d)
        orig = pg.run_cmd
        pg.run_cmd = self._fake_npm(["SKILL.md", "LICENSE"])
        try:
            code = pg.cmd_pack(argparse.Namespace(dir=str(self.d)))
        finally:
            pg.run_cmd = orig
        self.assertEqual(code, 2)

    def test_pack_local_fallback_finds_pyc(self):
        # 无 package.json → npm 失败 → 本地回退列举，pyc 应被检出
        make_self_use(self.d)
        write(self.d, "scripts/evil.pyc", "\x00")
        code = pg.cmd_pack(argparse.Namespace(dir=str(self.d)))
        self.assertEqual(code, 2)


class TestNames(TmpDir):
    def _fake(self, results):
        def fake(cmd, cwd=None, env=None, timeout=120):
            head = cmd[0]
            if "npm" in head.lower():
                code, out, err = results["npm"]
                return code, out, err
            if head == "gh":
                code, out, err = results["gh"]
                return code, out, err
            if head == "clawhub":
                code, out, err = results["clawhub"]
                return code, out, err
            return 127, "", "missing"
        return fake

    def test_all_free(self):
        make_complete(self.d)
        orig = pg.run_cmd
        pg.run_cmd = self._fake({
            "npm": (1, "", "E404 Not Found"),
            "gh": (1, "", "not found"),
            "clawhub": (0, "no match here\n", ""),
        })
        try:
            code = pg.cmd_names(argparse.Namespace(dir=str(self.d)))
        finally:
            pg.run_cmd = orig
        self.assertEqual(code, 0)

    def test_npm_taken(self):
        make_complete(self.d)
        orig = pg.run_cmd
        pg.run_cmd = self._fake({
            "npm": (0, "0.1.0\n", ""),
            "gh": (1, "", "not found"),
            "clawhub": (0, "no match\n", ""),
        })
        try:
            code = pg.cmd_names(argparse.Namespace(dir=str(self.d)))
        finally:
            pg.run_cmd = orig
        self.assertEqual(code, 2)

    def test_unknown_degrades(self):
        make_complete(self.d)
        orig = pg.run_cmd
        pg.run_cmd = self._fake({
            "npm": (127, "", ""),
            "gh": (127, "", ""),
            "clawhub": (127, "", ""),
        })
        try:
            code = pg.cmd_names(argparse.Namespace(dir=str(self.d)))
        finally:
            pg.run_cmd = orig
        self.assertEqual(code, 1)


class TestChannels(unittest.TestCase):
    def test_default_all(self):
        ns = argparse.Namespace(channels="", github_only=False)
        self.assertEqual(pg._channels_from_args(ns), ["github", "npm", "clawhub"])

    def test_github_only(self):
        ns = argparse.Namespace(channels="", github_only=True)
        self.assertEqual(pg._channels_from_args(ns), ["github"])

    def test_subset_dedup(self):
        ns = argparse.Namespace(channels="npm,npm,clawhub", github_only=False)
        self.assertEqual(pg._channels_from_args(ns), ["npm", "clawhub"])

    def test_empty_raises(self):
        ns = argparse.Namespace(channels="", github_only=False)
        with self.assertRaises(ValueError):
            pg._channels_from_args(argparse.Namespace(channels="x", github_only=False))


class TestPublish(TmpDir):
    def _args(self, **kw):
        base = dict(dir=str(self.d), dry_run=True, exec=False, force=False,
                    channels="", github_only=False, categories="",
                    topics="", description="", clawhub_owner="yottameta")
        base.update(kw)
        return argparse.Namespace(**base)

    def _capture(self, func, args):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = func(args)
        return code, buf.getvalue()

    def test_gate_blocked(self):
        code, out = self._capture(pg.cmd_publish, self._args())
        self.assertEqual(code, 2)
        self.assertIn("阻断", out)

    def test_dry_run_full_channels(self):
        make_complete(self.d)
        code, out = self._capture(pg.cmd_publish, self._args())
        self.assertEqual(code, 0)
        self.assertIn("gh repo create", out)
        self.assertIn("npm publish", out)
        self.assertIn("clawhub publish", out)
        self.assertIn("--name '元X yotta-x'", out)

    def test_dry_run_github_only(self):
        make_complete(self.d)
        code, out = self._capture(pg.cmd_publish, self._args(github_only=True))
        self.assertEqual(code, 0)
        self.assertIn("gh repo create", out)
        self.assertNotIn("npm publish", out)
        self.assertNotIn("clawhub publish", out)

    def test_dry_run_npm_only(self):
        make_complete(self.d)
        code, out = self._capture(pg.cmd_publish, self._args(channels="npm"))
        self.assertEqual(code, 0)
        self.assertNotIn("gh repo create", out)
        self.assertIn("npm publish", out)
        self.assertNotIn("clawhub publish", out)

    def test_github_mode_gate_on_minimal(self):
        # 只推 GitHub：无 package.json / 中英 README 也应通过闸门
        make_github(self.d)
        code, out = self._capture(pg.cmd_publish, self._args(github_only=True))
        self.assertEqual(code, 0)
        self.assertNotIn("阻断", out)

    def test_dry_run_plan_quotes(self):
        make_complete(self.d)
        code, out = self._capture(pg.cmd_publish, self._args(
            description="A description with spaces and 中文"))
        self.assertEqual(code, 0)
        self.assertIn("-m 'feat: initial release v0.1.0'", out)
        self.assertIn("--description 'A description with spaces and 中文'", out)
        self.assertIn("--name '元X yotta-x'", out)

    def test_shell_quote(self):
        self.assertEqual(pg._shell_quote("yotta-x"), "yotta-x")
        self.assertEqual(pg._shell_quote("元X yotta-x"), "'元X yotta-x'")
        self.assertEqual(pg._shell_quote("it's"), '"it\'s"')
        self.assertEqual(pg._shell_quote(""), "''")

    def test_dry_run_clawhub_owner(self):
        # 回归：clawhub publish 计划必须带 --owner yottameta（防发布到个人账号 @gon-kvs）
        make_complete(self.d)
        code, out = self._capture(pg.cmd_publish, self._args())
        self.assertEqual(code, 0)
        self.assertIn("clawhub publish", out)
        self.assertIn("--owner yottameta", out)

    def test_clawhub_owner_override(self):
        make_complete(self.d)
        code, out = self._capture(pg.cmd_publish, self._args(clawhub_owner="otherorg"))
        self.assertEqual(code, 0)
        self.assertIn("--owner otherorg", out)

    def test_gh_desc_truncated(self):
        make_complete(self.d)
        long_desc = "长描述描述描述描述 " * 60  # >350 字符
        code, out = self._capture(pg.cmd_publish, self._args(description=long_desc))
        self.assertEqual(code, 0)
        m = re.search(r"--description '([^']*)'", out)
        self.assertIsNotNone(m, "计划里应包含 --description")
        self.assertLessEqual(len(m.group(1)), 350)
        self.assertTrue(m.group(1).endswith("..."))

    def test_force_bypasses_gate(self):
        code, out = self._capture(pg.cmd_publish, self._args(force=True))
        self.assertEqual(code, 0)
        self.assertIn("--force 已显式授权", out)


class TestCheck(TmpDir):
    def _args(self, **kw):
        base = dict(dir=str(self.d), self_use=False, with_audit=False,
                    with_vetter=False, with_verify=False)
        base.update(kw)
        return argparse.Namespace(**base)

    def test_check_ready(self):
        make_complete(self.d)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = pg.cmd_check(self._args())
        self.assertEqual(code, 0)
        self.assertIn("READY", buf.getvalue())

    def test_check_blocked(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = pg.cmd_check(self._args())
        self.assertEqual(code, 2)
        self.assertIn("BLOCKED", buf.getvalue())

    def test_check_self_use(self):
        make_self_use(self.d)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = pg.cmd_check(self._args(self_use=True))
        self.assertEqual(code, 0)
        self.assertIn("自用模式", buf.getvalue())


class TestIsSecurity(unittest.TestCase):
    def test_non_security_exclusion(self):
        # 工具类技能即使描述含「审查」也不应误分类为安全家族
        self.assertFalse(pg.is_security("yotta-publish-guard",
                                        "发布前守门，含人工审查与版本对齐"))
        self.assertFalse(pg.is_security("yotta-skill-creator", "脚手架"))

    def test_family_security(self):
        self.assertTrue(pg.is_security("yotta-agent-hardening", "加固扫描"))
        self.assertTrue(pg.is_security("yotta-verify", "装前扫描器"))

    def test_keyword_security(self):
        self.assertTrue(pg.is_security("yotta-x", "威胁情报与审计"))
        self.assertFalse(pg.is_security("yotta-x", "文档写作工具"))



class TestGenericConfig(unittest.TestCase):
    """v0.2.0 通用化：scope/org/owner/topic 可配置，默认仍 yottameta。"""

    def test_default_config(self):
        cfg = pg.resolve_config(None)
        self.assertEqual(cfg.npm_scope, "@yottameta")
        self.assertEqual(cfg.github_org, "YottaMeta")
        self.assertEqual(cfg.clawhub_owner, "yottameta")
        self.assertEqual(cfg.topic, "yottaskills")

    def test_env_config(self):
        import os
        os.environ["YOTTA_GUARD_NPM_SCOPE"] = "@acme"
        os.environ["YOTTA_GUARD_GITHUB_ORG"] = "AcmeOrg"
        os.environ["YOTTA_GUARD_CLAWHUB_OWNER"] = "acme"
        os.environ["YOTTA_GUARD_TOPIC"] = "skills"
        try:
            cfg = pg.resolve_config(None)
            self.assertEqual(cfg.npm_scope, "@acme")
            self.assertEqual(cfg.github_org, "AcmeOrg")
            self.assertEqual(cfg.clawhub_owner, "acme")
            self.assertEqual(cfg.topic, "skills")
        finally:
            for k in ("YOTTA_GUARD_NPM_SCOPE", "YOTTA_GUARD_GITHUB_ORG",
                      "YOTTA_GUARD_CLAWHUB_OWNER", "YOTTA_GUARD_TOPIC"):
                os.environ.pop(k, None)

    def test_cli_config_overrides_env(self):
        import os
        os.environ["YOTTA_GUARD_NPM_SCOPE"] = "@acme"
        try:
            cfg = pg.resolve_config(argparse.Namespace(
                npm_scope="@other", github_org=None, clawhub_owner=None, topic=None))
            self.assertEqual(cfg.npm_scope, "@other")
        finally:
            os.environ.pop("YOTTA_GUARD_NPM_SCOPE", None)

    def test_validate_foreign_scope(self):
        """自定义 scope 校验：package.json name=@acme/yotta-x 通过（非强制 yottameta）。"""
        d = Path(tempfile.mkdtemp(prefix="pg-gen-"))
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        d = d / "yotta-x"
        d.mkdir()
        make_complete(d)
        write(d, "package.json", json.dumps(
            {"name": "@acme/yotta-x", "version": "0.1.0",
             "description": "测试", "license": "MIT",
             "files": ["SKILL.md", "LICENSE", "README.md", "README.zh-CN.md"]},
            ensure_ascii=False, indent=2))
        write(d, "README.md", README_EN.replace("@yottameta/yotta-x", "@acme/yotta-x")
              .replace("YottaMeta/yotta-x", "AcmeOrg/yotta-x"))
        write(d, "README.zh-CN.md", README_ZH.replace("@yottameta/yotta-x", "@acme/yotta-x")
              .replace("YottaMeta/yotta-x", "AcmeOrg/yotta-x"))
        cfg = pg.resolve_config(None)
        cfg.npm_scope, cfg.github_org = "@acme", "AcmeOrg"
        errors, _ = pg.validate_dir(d, mode="full", config=cfg)
        self.assertEqual(errors, [], "errors: %s" % errors)

    def test_validate_default_rejects_foreign_without_config(self):
        """默认配置下，自定义 scope 的 package name 应报错（保持 yottameta 默认）。"""
        d = Path(tempfile.mkdtemp(prefix="pg-gen2-"))
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        d = d / "yotta-x"
        d.mkdir()
        make_complete(d)
        write(d, "package.json", json.dumps(
            {"name": "@acme/yotta-x", "version": "0.1.0",
             "description": "测试", "license": "MIT",
             "files": ["SKILL.md", "LICENSE", "README.md", "README.zh-CN.md"]},
            ensure_ascii=False, indent=2))
        errors, _ = pg.validate_dir(d, mode="full")
        self.assertTrue(any("@yottameta" in e for e in errors), "errors: %s" % errors)

    def test_publish_plan_foreign_owner(self):
        """publish 计划按配置 org/owner/topic 生成（gh repo create / clawhub --owner / topic）。"""
        d = Path(tempfile.mkdtemp(prefix="pg-gen3-"))
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        d = d / "yotta-x"
        d.mkdir()
        make_complete(d)
        write(d, "README.md", README_EN.replace("@yottameta/yotta-x", "@acme/yotta-x")
              .replace("YottaMeta/yotta-x", "AcmeOrg/yotta-x"))
        write(d, "README.zh-CN.md", README_ZH.replace("@yottameta/yotta-x", "@acme/yotta-x")
              .replace("YottaMeta/yotta-x", "AcmeOrg/yotta-x"))
        write(d, "package.json", json.dumps(
            {"name": "@acme/yotta-x", "version": "0.1.0",
             "description": "测试", "license": "MIT",
             "files": ["SKILL.md", "LICENSE", "README.md", "README.zh-CN.md"]},
            ensure_ascii=False, indent=2))
        cfg = pg.resolve_config(None)
        cfg.npm_scope, cfg.github_org = "@acme", "AcmeOrg"
        cfg.clawhub_owner, cfg.topic = "acme", "skills"
        channels, plan, errors = pg._publish_plan(d, argparse.Namespace(
            github_only=False, channels="github,clawhub", description="",
            categories="productivity", topics="", clawhub_owner="acme"), config=cfg)
        self.assertEqual(errors, [])
        joined = " ".join(" ".join(c) if isinstance(c, list) else c for _, c in plan)
        self.assertIn("AcmeOrg/yotta-x", joined)
        self.assertIn("--owner acme", joined)
        self.assertIn("--add-topic skills", joined)
        self.assertNotIn("YottaMeta/yotta-x", joined)
        self.assertNotIn("--owner yottameta", joined)


if __name__ == "__main__":
    unittest.main()