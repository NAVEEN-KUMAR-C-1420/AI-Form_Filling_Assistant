# Extension Icons

This folder should contain PNG icons for the Chrome extension.

## Required Icons

- `icon16.png` - 16x16 pixels (toolbar)
- `icon48.png` - 48x48 pixels (extensions page)
- `icon128.png` - 128x128 pixels (Chrome Web Store)

## Creating Icons

You can use the provided SVG (`icon128.svg`) as a template and export to PNG at different sizes using:

### Using ImageMagick (Command Line)
```bash
convert icon128.svg -resize 16x16 icon16.png
convert icon128.svg -resize 48x48 icon48.png
convert icon128.svg -resize 128x128 icon128.png
```

### Using Online Tools
1. Go to https://svgtopng.com/
2. Upload `icon128.svg`
3. Download at different sizes

### Using Inkscape
1. Open `icon128.svg` in Inkscape
2. File > Export PNG Image
3. Set dimensions and export

## Icon Design

The icon represents:
- 📄 Document (white rectangle) - Document processing
- ✨ AI Sparkle (green circle) - AI-powered extraction
- 🇮🇳 India colors accent - Made for Indian government services

## Placeholder Icons

For development, you can use simple colored squares:

```python
# Python script to create placeholder icons
from PIL import Image

for size in [16, 48, 128]:
    img = Image.new('RGB', (size, size), color='#4F46E5')
    img.save(f'icon{size}.png')
```
