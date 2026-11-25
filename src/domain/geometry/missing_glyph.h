/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */
#pragma once
// gfxFontMissingGlyphs::DrawMissingGlyph, projected into neutral rectangles.
// Coordinates are user-space pixels; the drawing owner applies its normal
// transform, clipping, composition and shadow. A missing glyph is not glyph 0
// of an arbitrary fallback font, and does not acquire synthetic italic skew.
#include <algorithm>
#include <cmath>
#include <cstdint>

namespace ruyijs::domain::geometry {
struct MissingGlyph {
  uint32_t codepoint = 0;
  float x = 0, y = 0, width = 0, height = 0;
};

template <class DrawRect>
void DrawMissingGlyph(const MissingGlyph& glyph, DrawRect draw) {
  const float x = glyph.x, y = glyph.y, w = glyph.width, h = glyph.height;
  if (!(w > 3 && h > 1)) return;
  // One-pixel border, horizontally inset by one pixel, at half opacity.
  draw(x + 1, y, w - 2, 1.0f, 0.5f);
  draw(x + 1, y + h - 1, w - 2, 1.0f, 0.5f);
  if (h > 2) {
    draw(x + 1, y + 1, 1.0f, h - 2, 0.5f);
    draw(x + w - 2, y + 1, 1.0f, h - 2, 0.5f);
  }
  const int columns = glyph.codepoint < 0x10000 ? 2 : 3;
  if (w < columns * 4 || h < 11) return;
  const float scale = std::max(1.0f, std::floor(std::min(h / 13, w / (columns * 4 + 1))));
  // Rows of the donor's 3x5 hexadecimal mini-font, most significant bit left.
  static constexpr uint8_t digits[16][5] = {
      {2,5,5,5,2}, {2,2,2,2,2}, {7,1,7,4,7}, {7,1,7,1,7},
      {5,5,7,1,1}, {7,4,7,1,7}, {7,4,7,5,7}, {7,1,1,1,1},
      {7,5,7,5,7}, {7,5,7,1,1}, {7,5,7,5,5}, {6,5,6,5,6},
      {3,4,4,4,3}, {6,5,5,5,6}, {7,4,7,4,7}, {7,4,7,4,4}};
  const float left = columns == 2 ? -3.5f : -5.5f;
  for (int index = 0; index < columns * 2; ++index) {
    const unsigned digit = (glyph.codepoint >> (4 * (columns * 2 - index - 1))) & 15;
    const float dx = x + w / 2 + (left + (index % columns) * 4) * scale;
    const float dy = y + h / 2 + (index < columns ? -5.5f : 0.5f) * scale;
    for (int row = 0; row < 5; ++row)
      for (int col = 0; col < 3; ++col)
        if (digits[digit][row] & (1 << (2 - col)))
          draw(dx + col * scale, dy + row * scale, scale, scale, 1.0f);
  }
}
}  // namespace ruyijs::domain::geometry
