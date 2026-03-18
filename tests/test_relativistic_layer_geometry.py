import unittest

from ai_from_scratch.relativistic_layer_geometry import (
    derive_spacetime_from_classical_layer_geometry,
    galilean_boost,
    lorentz_boost,
    lorentz_gamma,
    minkowski_interval,
)


class RelativisticLayerGeometryTests(unittest.TestCase):
    def test_lorentz_gamma_starts_at_one(self) -> None:
        self.assertAlmostEqual(1.0, lorentz_gamma(0.0), places=9)

    def test_lorentz_boost_preserves_interval(self) -> None:
        event = (2.0, 0.8, 0.3, 0.1)
        transformed = lorentz_boost(event, 0.6)
        self.assertAlmostEqual(minkowski_interval(event), minkowski_interval(transformed), places=9)

    def test_galilean_boost_breaks_null_cone(self) -> None:
        null_event = (1.0, 1.0, 0.0, 0.0)
        transformed = galilean_boost(null_event, 0.6)
        self.assertGreater(abs(minkowski_interval(transformed)), 0.1)

    def test_derivation_selects_lorentzian_geometry(self) -> None:
        report = derive_spacetime_from_classical_layer_geometry()
        self.assertEqual("lorentzian_minkowski", report["winner"]["name"])
        self.assertEqual(["lorentzian_minkowski"], report["passing_geometries"])
        self.assertTrue(report["lorentzian_unique"])
        self.assertEqual("ds^2 = c^2 dt^2 - dx^2 - dy^2 - dz^2", report["derived_metric"])


if __name__ == "__main__":
    unittest.main()
