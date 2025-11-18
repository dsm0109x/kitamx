# Favicon Generation Instructions

## Required Files

Generate the following favicon sizes from `kita-logo-negro.png`:

```bash
# Install ImageMagick if not present
sudo apt install imagemagick

# Generate all sizes
convert ../kita-logo-negro.png -resize 16x16 favicon-16x16.png
convert ../kita-logo-negro.png -resize 32x32 favicon-32x32.png
convert ../kita-logo-negro.png -resize 180x180 apple-touch-icon.png
convert ../kita-logo-negro.png -resize 192x192 android-chrome-192x192.png
convert ../kita-logo-negro.png -resize 512x512 android-chrome-512x512.png
```

## Required Files List

- [ ] `favicon-16x16.png` (16x16px)
- [ ] `favicon-32x32.png` (32x32px)
- [ ] `apple-touch-icon.png` (180x180px)
- [ ] `android-chrome-192x192.png` (192x192px)
- [ ] `android-chrome-512x512.png` (512x512px)
- [x] `site.webmanifest` (already created)

## Usage

Once generated, these files are referenced in `base_minimal.html` and provide optimal favicon display across all devices and browsers.
