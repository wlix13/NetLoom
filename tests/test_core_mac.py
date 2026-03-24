"""Tests for netloom.core.mac module."""

import pytest

from netloom.core.mac import _set_locally_administered, generate_mac


class TestSetLocallyAdministered:
    """Test _set_locally_administered helper function."""

    def test_sets_locally_administered_bit(self):
        """Should set bit 1 (locally administered) in first byte."""
        mac_bytes = bytearray([0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        _set_locally_administered(mac_bytes)
        assert mac_bytes[0] & 0x02 == 0x02

    def test_unsets_multicast_bit(self):
        """Should unset bit 0 (multicast) in first byte."""
        mac_bytes = bytearray([0xFF, 0x00, 0x00, 0x00, 0x00, 0x00])
        _set_locally_administered(mac_bytes)
        assert mac_bytes[0] & 0x01 == 0x00

    def test_preserves_other_bits(self):
        """Should preserve other bits in the MAC address."""
        mac_bytes = bytearray([0xF0, 0xAB, 0xCD, 0xEF, 0x12, 0x34])
        _set_locally_administered(mac_bytes)
        # First byte should have locally administered bit set and multicast unset
        assert mac_bytes[0] & 0x02 == 0x02
        assert mac_bytes[0] & 0x01 == 0x00
        # Other bytes unchanged
        assert mac_bytes[1] == 0xAB
        assert mac_bytes[2] == 0xCD
        assert mac_bytes[3] == 0xEF
        assert mac_bytes[4] == 0x12
        assert mac_bytes[5] == 0x34


class TestGenerateMac:
    """Test generate_mac function."""

    def test_returns_mac_format(self):
        """Generated MAC should be in XX:XX:XX:XX:XX:XX format."""
        mac = generate_mac(seed="test")
        parts = mac.split(":")
        assert len(parts) == 6
        for part in parts:
            assert len(part) == 2
            # Should be valid hex
            int(part, 16)

    def test_uppercase_format(self):
        """MAC address should be in uppercase."""
        mac = generate_mac(seed="test")
        assert mac == mac.upper()

    def test_deterministic_with_seed(self):
        """Same seed should produce same MAC."""
        mac1 = generate_mac(seed="test123")
        mac2 = generate_mac(seed="test123")
        assert mac1 == mac2

    def test_different_seeds_produce_different_macs(self):
        """Different seeds should produce different MACs."""
        mac1 = generate_mac(seed="seed1")
        mac2 = generate_mac(seed="seed2")
        assert mac1 != mac2

    def test_locally_administered_bit_set(self):
        """Generated MAC should have locally administered bit set."""
        mac = generate_mac(seed="test")
        first_byte = int(mac.split(":")[0], 16)
        assert first_byte & 0x02 == 0x02

    def test_multicast_bit_unset(self):
        """Generated MAC should not have multicast bit set."""
        mac = generate_mac(seed="test")
        first_byte = int(mac.split(":")[0], 16)
        assert first_byte & 0x01 == 0x00

    def test_random_mac_when_random_flag_true(self):
        """When random_mac=True, should generate random MAC."""
        mac1 = generate_mac(random_mac=True)
        mac2 = generate_mac(random_mac=True)
        # Very unlikely to be the same (1 in 2^48)
        assert mac1 != mac2

    def test_random_mac_when_seed_none(self):
        """When seed=None, should generate random MAC."""
        mac1 = generate_mac(seed=None)
        mac2 = generate_mac(seed=None)
        # Very unlikely to be the same
        assert mac1 != mac2

    def test_random_flag_overrides_seed(self):
        """random_mac=True should override provided seed."""
        mac1 = generate_mac(seed="test", random_mac=True)
        mac2 = generate_mac(seed="test", random_mac=True)
        # Should be random even with same seed
        assert mac1 != mac2

    def test_valid_mac_structure(self):
        """Generated MAC should be structurally valid."""
        mac = generate_mac(seed="structure_test")
        # Check format
        assert len(mac) == 17  # XX:XX:XX:XX:XX:XX
        assert mac.count(":") == 5
        # Check all parts are hex
        for part in mac.split(":"):
            assert 0 <= int(part, 16) <= 255

    def test_empty_seed(self):
        """Empty string seed should produce deterministic MAC."""
        mac1 = generate_mac(seed="")
        mac2 = generate_mac(seed="")
        assert mac1 == mac2

    def test_long_seed(self):
        """Long seed should be handled correctly."""
        long_seed = "a" * 1000
        mac1 = generate_mac(seed=long_seed)
        mac2 = generate_mac(seed=long_seed)
        assert mac1 == mac2
        # Should still be valid MAC
        assert len(mac1.split(":")) == 6