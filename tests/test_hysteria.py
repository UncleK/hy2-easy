import importlib.util
from pathlib import Path
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('render_hysteria', ROOT / 'scripts/render_hysteria.py')
renderer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(renderer)


class HysteriaRecoveryTests(unittest.TestCase):
    def test_password_with_yaml_characters_roundtrips_without_config_changes(self):
        password = 'test-only: # quote" newline\nsecond-line'
        actual = yaml.safe_load(renderer.render(password))
        expected = yaml.safe_load((ROOT / 'infra/hysteria.config.template.yaml').read_text())
        self.assertEqual(actual['auth']['password'], password)
        actual['auth']['password'] = expected['auth']['password']
        self.assertEqual(actual, expected)

    def test_missing_or_placeholder_secret_rejected(self):
        for password in (None, '', 'REPLACE_WITH_HYSTERIA_PASSWORD'):
            with self.assertRaises(ValueError):
                renderer.render(password)


if __name__ == '__main__':
    unittest.main()
