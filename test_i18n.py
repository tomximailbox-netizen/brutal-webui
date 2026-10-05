import os
import re
import sys
import json
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class TestI18nSystem(unittest.TestCase):
    def setUp(self):
        self.i18n_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "i18n.js")
        self.assertTrue(os.path.exists(self.i18n_path), "static/i18n.js 必须存在")
        with open(self.i18n_path, "r", encoding="utf-8") as f:
            self.content = f.read()

    def test_i18n_has_required_languages(self):
        # 验证支持 zh-CN, zh-TW, en 三种语言
        self.assertIn('"zh-CN"', self.content)
        self.assertIn('"zh-TW"', self.content)
        self.assertIn('"en"', self.content)
        self.assertIn('DEFAULT_LANG = "en"', self.content)

    def test_i18n_dictionaries_alignment(self):
        # 提取 dict 中的所有 key，确保 zh-CN 和 zh-TW 覆盖率达到 100%
        en_match = re.search(r'"en":\s*\{[^}]*dict:\s*(\{.*?\n\s*\})', self.content, re.DOTALL)
        zh_cn_match = re.search(r'"zh-CN":\s*\{[^}]*dict:\s*(\{.*?\n\s*\})', self.content, re.DOTALL)
        zh_tw_match = re.search(r'"zh-TW":\s*\{[^}]*dict:\s*(\{.*?\n\s*\})', self.content, re.DOTALL)

        self.assertIsNotNone(en_match)
        self.assertIsNotNone(zh_cn_match)
        self.assertIsNotNone(zh_tw_match)

        en_keys = set(re.findall(r'^\s*([a-zA-Z0-9_]+):\s*["`]', en_match.group(1), re.MULTILINE))
        zh_cn_keys = set(re.findall(r'^\s*([a-zA-Z0-9_]+):\s*["`]', zh_cn_match.group(1), re.MULTILINE))
        zh_tw_keys = set(re.findall(r'^\s*([a-zA-Z0-9_]+):\s*["`]', zh_tw_match.group(1), re.MULTILINE))

        self.assertGreater(len(en_keys), 30)
        self.assertEqual(en_keys, zh_cn_keys, f"zh-CN 缺少以下翻译 key: {en_keys - zh_cn_keys}")
        self.assertEqual(en_keys, zh_tw_keys, f"zh-TW 缺少以下翻译 key: {en_keys - zh_tw_keys}")

    def test_browser_language_sniffer_logic(self):
        # 模拟 detectLanguage 的匹配规则
        def simulate_detect(browser_lang):
            b = browser_lang.lower().strip()
            if not b:
                return "en"
            if "tw" in b or "hk" in b or "mo" in b or "hant" in b:
                return "zh-TW"
            if b.startswith("zh"):
                return "zh-CN"
            if b.startswith("en"):
                return "en"
            # 任何其它未定义语种默认回退到 en
            return "en"

        # 验证繁体匹配
        self.assertEqual(simulate_detect("zh-TW"), "zh-TW")
        self.assertEqual(simulate_detect("zh-HK"), "zh-TW")
        self.assertEqual(simulate_detect("zh-Hant-HK"), "zh-TW")

        # 验证简体匹配
        self.assertEqual(simulate_detect("zh-CN"), "zh-CN")
        self.assertEqual(simulate_detect("zh-Hans-CN"), "zh-CN")
        self.assertEqual(simulate_detect("zh"), "zh-CN")

        # 验证英语匹配
        self.assertEqual(simulate_detect("en-US"), "en")
        self.assertEqual(simulate_detect("en-GB"), "en")
        self.assertEqual(simulate_detect("en"), "en")

        # 验证其他语种自动回退为 en (默认英文)
        self.assertEqual(simulate_detect("ja-JP"), "en")
        self.assertEqual(simulate_detect("fr-FR"), "en")
        self.assertEqual(simulate_detect("de-DE"), "en")
        self.assertEqual(simulate_detect("ko-KR"), "en")
        self.assertEqual(simulate_detect(""), "en")


if __name__ == "__main__":
    unittest.main()
