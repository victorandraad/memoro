"""Código de terceiro vendorizado: o arquivo é o que a licença registra, byte a byte."""
from __future__ import annotations

import hashlib
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SHA_D3 = "ad87c67d0ffc5fb76ececb848c79082d752ee928bb7b3d30fada14b0c39cb695"


class TestD3Vendorizado(unittest.TestCase):
    def test_sha256_bate_com_o_fixado(self):
        blob = (RAIZ / "memoro" / "d3-hierarchy.min.js").read_bytes()
        self.assertEqual(hashlib.sha256(blob).hexdigest(), SHA_D3)

    def test_sha256_esta_registrado_nas_licencas(self):
        self.assertIn(SHA_D3, (RAIZ / "LICENCAS-DE-TERCEIROS.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
