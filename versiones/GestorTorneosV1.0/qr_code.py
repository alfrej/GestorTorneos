"""
Minimal QR code generator based on Nayuki's qrcodegen (MIT License).
Source: https://www.nayuki.io/page/qr-code-generator-library
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


class QrCode:
    @dataclass(frozen=True)
    class Ecc:
        ordinal: int
        format_bits: int

    Ecc.LOW = Ecc(0, 1)       # 7% error correction
    Ecc.MEDIUM = Ecc(1, 0)    # 15% error correction
    Ecc.QUARTILE = Ecc(2, 3)  # 25% error correction
    Ecc.HIGH = Ecc(3, 2)      # 30% error correction

    MIN_VERSION = 1
    MAX_VERSION = 40

    def __init__(self, version: int, err_corr: "QrCode.Ecc", data_codewords: List[int], mask: int):
        if not (QrCode.MIN_VERSION <= version <= QrCode.MAX_VERSION):
            raise ValueError("Version fuera de rango")
        if not (-1 <= mask <= 7):
            raise ValueError("Mascara fuera de rango")
        self._version = version
        self._err_corr = err_corr
        self._size = version * 4 + 17
        self._modules = [[False] * self._size for _ in range(self._size)]
        self._is_function = [[False] * self._size for _ in range(self._size)]
        self._draw_function_patterns()
        self._draw_codewords(data_codewords)
        self._apply_mask(mask)
        self._draw_format_bits(mask)
        self._draw_version()

    @staticmethod
    def encode_text(text: str, ecl: "QrCode.Ecc") -> "QrCode":
        seg = QrSegment.make_bytes(text.encode("utf-8"))
        return QrCode.encode_segments([seg], ecl)

    @staticmethod
    def encode_segments(segs: List["QrSegment"], ecl: "QrCode.Ecc") -> "QrCode":
        if not segs:
            return QrCode(1, ecl, QrCode._create_codewords(1, ecl, [0]), 0)
        for version in range(QrCode.MIN_VERSION, QrCode.MAX_VERSION + 1):
            data_capacity = QrCode._get_num_data_codewords(version, ecl) * 8
            data_used = QrSegment.get_total_bits(segs, version)
            if data_used <= data_capacity:
                bit_buffer: List[int] = []
                for seg in segs:
                    seg._write(bit_buffer, version)
                terminator = min(4, data_capacity - len(bit_buffer))
                bit_buffer.extend([0] * terminator)
                while len(bit_buffer) % 8 != 0:
                    bit_buffer.append(0)
                pad_bytes = [0xEC, 0x11]
                i = 0
                while len(bit_buffer) < data_capacity:
                    QrCode._append_bits(bit_buffer, pad_bytes[i & 1], 8)
                    i += 1
                data_codewords = [0] * (len(bit_buffer) // 8)
                for i in range(len(bit_buffer)):
                    data_codewords[i // 8] |= bit_buffer[i] << (7 - (i % 8))
                return QrCode(version, ecl, QrCode._create_codewords(version, ecl, data_codewords), QrCode._select_mask())
        raise ValueError("Datos demasiado largos")

    def get_size(self) -> int:
        return self._size

    def get_module(self, x: int, y: int) -> bool:
        return self._modules[y][x]

    def _draw_function_patterns(self) -> None:
        self._draw_finder(3, 3)
        self._draw_finder(self._size - 4, 3)
        self._draw_finder(3, self._size - 4)
        self._draw_align_patterns()
        self._draw_timing_patterns()
        self._draw_dark_module()
        self._draw_format_bits(0)

    def _draw_finder(self, x: int, y: int) -> None:
        for dy in range(-4, 5):
            for dx in range(-4, 5):
                xx = x + dx
                yy = y + dy
                if 0 <= xx < self._size and 0 <= yy < self._size:
                    dist = max(abs(dx), abs(dy))
                    self._modules[yy][xx] = dist in (0, 1, 2)
                    self._is_function[yy][xx] = True

    def _draw_align_patterns(self) -> None:
        positions = QrCode._get_alignment_positions(self._version)
        for i in positions:
            for j in positions:
                if (i == 6 and j == 6) or (i == 6 and j == self._size - 7) or (i == self._size - 7 and j == 6):
                    continue
                self._draw_alignment(i, j)

    def _draw_alignment(self, x: int, y: int) -> None:
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                self._modules[y + dy][x + dx] = max(abs(dx), abs(dy)) != 1
                self._is_function[y + dy][x + dx] = True

    def _draw_timing_patterns(self) -> None:
        for i in range(self._size):
            self._modules[6][i] = (i % 2 == 0)
            self._modules[i][6] = (i % 2 == 0)
            self._is_function[6][i] = True
            self._is_function[i][6] = True

    def _draw_dark_module(self) -> None:
        self._modules[self._size - 8][8] = True
        self._is_function[self._size - 8][8] = True

    def _draw_format_bits(self, mask: int) -> None:
        data = self._err_corr.format_bits << 3 | mask
        rem = data
        for _ in range(10):
            rem = (rem << 1) ^ ((rem >> 9) * 0x537)
        bits = ((data << 10) | rem) ^ 0x5412
        for i in range(15):
            bit = (bits >> i) & 1
            a = [0, 1, 2, 3, 4, 5, 7, 8, self._size - 7, self._size - 6, self._size - 5, self._size - 4, self._size - 3, self._size - 2, self._size - 1][i]
            self._modules[8][a] = bool(bit)
            self._is_function[8][a] = True
            b = [self._size - 1, self._size - 2, self._size - 3, self._size - 4, self._size - 5, self._size - 6, self._size - 7, 7, 5, 4, 3, 2, 1, 0, 8][i]
            self._modules[b][8] = bool(bit)
            self._is_function[b][8] = True

    def _draw_version(self) -> None:
        if self._version < 7:
            return
        rem = self._version
        for _ in range(12):
            rem = (rem << 1) ^ ((rem >> 11) * 0x1F25)
        bits = (self._version << 12) | rem
        for i in range(18):
            bit = (bits >> i) & 1
            a = self._size - 11 + (i % 3)
            b = i // 3
            self._modules[b][a] = bool(bit)
            self._is_function[b][a] = True
            self._modules[a][b] = bool(bit)
            self._is_function[a][b] = True

    def _draw_codewords(self, data: List[int]) -> None:
        i = 0
        right = self._size - 1
        while right > 0:
            if right == 6:
                right -= 1
            for vert in range(self._size):
                y = self._size - 1 - vert if ((right + 1) & 2) == 0 else vert
                for x in (right, right - 1):
                    if not self._is_function[y][x]:
                        bit = False
                        if i < len(data) * 8:
                            bit = ((data[i >> 3] >> (7 - (i & 7))) & 1) != 0
                            i += 1
                        self._modules[y][x] = bit
            right -= 2

    def _apply_mask(self, mask: int) -> None:
        if mask == -1:
            return
        for y in range(self._size):
            for x in range(self._size):
                if self._is_function[y][x]:
                    continue
                invert = False
                if mask == 0:
                    invert = (x + y) % 2 == 0
                elif mask == 1:
                    invert = y % 2 == 0
                elif mask == 2:
                    invert = x % 3 == 0
                elif mask == 3:
                    invert = (x + y) % 3 == 0
                elif mask == 4:
                    invert = (x // 3 + y // 2) % 2 == 0
                elif mask == 5:
                    invert = (x * y) % 2 + (x * y) % 3 == 0
                elif mask == 6:
                    invert = ((x * y) % 2 + (x * y) % 3) % 2 == 0
                elif mask == 7:
                    invert = ((x + y) % 2 + (x * y) % 3) % 2 == 0
                if invert:
                    self._modules[y][x] = not self._modules[y][x]

    @staticmethod
    def _get_alignment_positions(ver: int) -> List[int]:
        if ver == 1:
            return []
        num = ver // 7 + 2
        step = 26 if ver == 32 else (ver * 4 + num * 2 + 1) // (num * 2 - 2) * 2
        positions = [6]
        pos = ver * 4 + 10
        for _ in range(num - 1):
            positions.insert(1, pos)
            pos -= step
        return positions

    @staticmethod
    def _get_num_data_codewords(ver: int, ecl: "QrCode.Ecc") -> int:
        return QrCode._NUM_DATA_CODEWORDS[ecl.ordinal][ver]

    @staticmethod
    def _append_bits(bit_buffer: List[int], value: int, length: int) -> None:
        for i in range(length - 1, -1, -1):
            bit_buffer.append((value >> i) & 1)

    @staticmethod
    def _select_mask() -> int:
        return 0

    @staticmethod
    def _create_codewords(ver: int, ecl: "QrCode.Ecc", data: List[int]) -> List[int]:
        num_blocks = QrCode._NUM_ERROR_CORRECTION_BLOCKS[ecl.ordinal][ver]
        raw_codewords = QrCode._NUM_RAW_DATA_MODULES[ver] // 8
        data_len = QrCode._get_num_data_codewords(ver, ecl)
        block_ec_len = (raw_codewords - data_len) // num_blocks
        short_block_len = raw_codewords // num_blocks
        num_short_blocks = num_blocks - (raw_codewords % num_blocks)
        short_data_len = short_block_len - block_ec_len
        data_blocks = []
        rs_blocks = []
        k = 0
        for i in range(num_blocks):
            dat_len = short_data_len if i < num_short_blocks else short_data_len + 1
            dat = data[k:k + dat_len]
            k += dat_len
            data_blocks.append(dat)
            rs_blocks.append(QrCode._reed_solomon_compute(dat, block_ec_len))
        result = []
        for i in range(short_block_len):
            for r in range(num_blocks):
                if i < len(data_blocks[r]):
                    result.append(data_blocks[r][i])
        for i in range(block_ec_len):
            for r in range(num_blocks):
                result.append(rs_blocks[r][i])
        return result

    @staticmethod
    def _reed_solomon_compute(data: List[int], ecc_len: int) -> List[int]:
        result = [0] * ecc_len
        for b in data:
            factor = b ^ result[0]
            result = result[1:] + [0]
            for i in range(ecc_len):
                result[i] ^= QrCode._reed_solomon_multiply(QrCode._reed_solomon_divisor(ecc_len)[i], factor)
        return result

    @staticmethod
    def _reed_solomon_divisor(degree: int) -> List[int]:
        result = [1]
        root = 1
        for _ in range(degree):
            result.append(0)
            for i in range(len(result) - 1):
                result[i] = QrCode._reed_solomon_multiply(result[i], root) ^ result[i + 1]
            root = QrCode._reed_solomon_multiply(root, 0x02)
        return result

    @staticmethod
    def _reed_solomon_multiply(x: int, y: int) -> int:
        z = 0
        for i in range(8):
            if (y >> i) & 1:
                z ^= x << i
        for i in range(14, 7, -1):
            if (z >> i) & 1:
                z ^= 0x11D << (i - 8)
        return z & 0xFF

    _NUM_DATA_CODEWORDS = [
        [-1, 19, 34, 55, 80, 108, 136, 156, 194, 232, 274, 324, 370, 428, 461, 523, 589, 647, 721, 795, 861, 932, 1006, 1094, 1174, 1276, 1370, 1468, 1531, 1631, 1735, 1843, 1955, 2071, 2191, 2306, 2434, 2566, 2702, 2812, 2956],
        [-1, 16, 28, 44, 64, 86, 108, 124, 154, 182, 216, 254, 290, 334, 365, 415, 453, 507, 563, 627, 669, 714, 782, 860, 914, 1000, 1062, 1128, 1193, 1267, 1373, 1455, 1541, 1631, 1725, 1812, 1914, 1992, 2102, 2216, 2334],
        [-1, 13, 22, 34, 48, 62, 76, 88, 110, 132, 154, 180, 206, 244, 261, 295, 325, 367, 397, 445, 485, 512, 568, 614, 664, 718, 754, 808, 871, 911, 985, 1033, 1115, 1171, 1231, 1286, 1354, 1426, 1502, 1582, 1666],
        [-1, 9, 16, 26, 36, 46, 60, 66, 86, 100, 122, 140, 158, 180, 197, 223, 253, 283, 313, 341, 385, 406, 442, 464, 514, 538, 596, 628, 661, 701, 745, 793, 845, 901, 961, 986, 1054, 1096, 1142, 1222, 1276],
    ]

    _NUM_ERROR_CORRECTION_BLOCKS = [
        [-1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 4, 4, 4, 4, 4, 6, 6, 6, 6, 7, 8, 8, 9, 9, 10, 12, 12, 12, 13, 14, 15, 16, 17, 18, 19, 19, 20, 21, 22, 24, 25],
        [-1, 1, 1, 1, 2, 2, 4, 4, 4, 5, 5, 5, 8, 9, 9, 10, 10, 11, 13, 14, 16, 17, 17, 18, 20, 21, 23, 25, 26, 28, 29, 31, 33, 35, 37, 38, 40, 43, 45, 47, 49],
        [-1, 1, 1, 2, 2, 4, 4, 6, 6, 8, 8, 8, 10, 12, 12, 14, 16, 16, 18, 21, 22, 24, 24, 26, 28, 30, 31, 33, 35, 37, 38, 40, 43, 45, 47, 49, 51, 53, 56, 59, 62],
        [-1, 1, 1, 2, 4, 4, 4, 5, 6, 8, 8, 11, 11, 16, 16, 18, 16, 19, 21, 25, 25, 25, 34, 30, 32, 35, 37, 40, 42, 45, 48, 51, 54, 57, 60, 63, 66, 70, 74, 77, 81],
    ]

    _NUM_RAW_DATA_MODULES = [
        -1, 208, 359, 567, 807, 1079, 1383, 1568, 1936, 2336, 2768, 3232, 3728, 4256, 4651, 5243, 5867, 6523, 7211, 7931, 8683, 9252, 10068, 10952, 11796, 12732, 13628, 14628, 15371, 16411, 17483, 18587, 19723, 20891, 22091, 23008, 24272, 25568, 26896, 28256, 29648,
    ]


class QrSegment:
    def __init__(self, mode: "QrSegment.Mode", num_chars: int, bit_data: List[int]):
        self._mode = mode
        self._num_chars = num_chars
        self._bit_data = bit_data

    @dataclass(frozen=True)
    class Mode:
        mode_bits: int
        num_bits_char_count: List[int]

    Mode.BYTE = Mode(4, [8, 16, 16])

    @staticmethod
    def make_bytes(data: bytes) -> "QrSegment":
        bit_data: List[int] = []
        for b in data:
            for i in range(7, -1, -1):
                bit_data.append((b >> i) & 1)
        return QrSegment(QrSegment.Mode.BYTE, len(data), bit_data)

    def _write(self, bit_buffer: List[int], version: int) -> None:
        QrCode._append_bits(bit_buffer, self._mode.mode_bits, 4)
        num_bits = self._mode.num_bits_char_count[0 if version <= 9 else 1 if version <= 26 else 2]
        QrCode._append_bits(bit_buffer, self._num_chars, num_bits)
        bit_buffer.extend(self._bit_data)

    @staticmethod
    def get_total_bits(segs: List["QrSegment"], version: int) -> int:
        result = 0
        for seg in segs:
            ccbits = seg._mode.num_bits_char_count[0 if version <= 9 else 1 if version <= 26 else 2]
            if seg._num_chars >= (1 << ccbits):
                return 10 ** 18
            result += 4 + ccbits + len(seg._bit_data)
        return result
