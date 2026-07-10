"""BDD tests: PCM format conversion (int16 <-> float32).

These pure functions are the crux of the audio pipeline — LiveKit speaks int16,
Comni speaks float32. A round-trip must preserve signal within quantization error.
"""

import numpy as np

from livekit_bridge import float32_to_int16, int16_to_float32
from tests.expectations import expect


class DescribeInt16ToFloat32:
    def it_maps_full_scale_int16_into_unit_range(self):
        # /32768: -32768 -> exactly -1.0; 32767 -> just under 1.0; all within [-1, 1]
        out = np.frombuffer(int16_to_float32(np.array([32767, -32768], dtype=np.int16).tobytes()),
                            dtype=np.float32)
        expect(float(out[1])).to_equal(-1.0)
        expect(float(out[0])).to_be_truthy()
        assert -1.0 <= float(out[0]) <= 1.0

    def it_produces_float32_output(self):
        out = int16_to_float32(np.int16(0).tobytes())
        out_arr = np.frombuffer(out, dtype=np.float32)
        expect(out_arr.dtype).to_equal(np.float32)

    def it_preserves_sample_count(self):
        samples = np.arange(-100, 100, dtype=np.int16)
        out = np.frombuffer(int16_to_float32(samples.tobytes()), dtype=np.float32)
        expect(len(out)).to_equal(len(samples))


class DescribeFloat32ToInt16:
    def it_clips_overflow(self):
        out = float32_to_int16(np.array([2.0, -2.0], dtype=np.float32).tobytes())
        expect(int(out[0])).to_equal(32767)
        expect(int(out[1])).to_equal(-32768)

    def it_produces_int16_output(self):
        out = float32_to_int16(np.float32(0.0).tobytes())
        expect(out.dtype).to_equal(np.int16)


class DescribeRoundTrip:
    def it_round_trips_mid_range_values_exactly(self):
        original = np.array([0, 100, -100, 16000, -16000], dtype=np.int16)
        as_float = int16_to_float32(original.tobytes())
        restored = float32_to_int16(as_float)
        np.testing.assert_array_equal(restored, original)

    def it_round_trips_extremes_within_quantization_tolerance(self):
        # /32768 forward and *32767 reverse differ by ±1 LSB at full scale
        original = np.array([32767, -32768], dtype=np.int16)
        restored = float32_to_int16(int16_to_float32(original.tobytes()))
        assert np.abs(restored.astype(int) - original.astype(int)).max() <= 2
