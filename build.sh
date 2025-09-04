#!/bin/bash
set -eo pipefail

if [[ -z "$ROM_TYPE" ]]; then
  echo "❌ ROM_TYPE environment variable not set!"
  exit 1
fi

if [[ "$ROM_TYPE" != "aosp" && "$ROM_TYPE" != "miui" ]]; then
  echo "❌ Invalid ROM type: $ROM_TYPE. Use 'aosp' or 'miui'."
  exit 1
fi

DIR=$(pwd)
OUT_DIR="out_$ROM_TYPE"
CONFIG_DIR="arch/arm64/configs"
ARTIFACT_DIR="${OUT_DIR}/artifact"
ZIMAGE_DIR="${OUT_DIR}/arch/arm64/boot"
KERNEL_DEFCONFIG="munch_defconfig"
BUILD_START=$(date +"%s")

# Debugging
echo "🔧 ROM Type: $ROM_TYPE"
echo "🔧 KPM: $kpm"
echo "🔧 ZIP_NAME_BASE: $ZIP_NAME_BASE"

export PATH="$DIR/clang/bin:$PATH"
export ARCH=arm64
export SUBARCH=arm64
export KBUILD_BUILD_USER="Uday"
export KBUILD_BUILD_HOST="Github"
export KBUILD_BUILD_TIMESTAMP="$(TZ=Asia/Kolkata date)"
export KBUILD_COMPILER_STRING="$($DIR/clang/bin/clang --version | head -n 1 | perl -pe 's///gs' | sed -e 's/  / /g' -e 's/[[:space:]]$//')"

echo "🧹 Cleaning previous build..."
rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR"

# Optional KPM config
if [[ "$kpm" == "true" ]]; then
  echo "🔧 Adding KPM configs to defconfig..."
  echo "CONFIG_KALLSYMS=y" >> "$CONFIG_DIR/$KERNEL_DEFCONFIG"
  echo "CONFIG_KALLSYMS_ALL=y" >> "$CONFIG_DIR/$KERNEL_DEFCONFIG"
  echo "CONFIG_KPM=y" >> "$CONFIG_DIR/$KERNEL_DEFCONFIG"
fi

# MIUI-specific patches
if [[ "$ROM_TYPE" == "miui" ]]; then
  echo "🔧 Adjusting panel dimensions for HyperOS..."
  sed -i 's/qcom,mdss-pan-physical-width-dimension = <70>;$/qcom,mdss-pan-physical-width-dimension = <695>;/' arch/arm64/boot/dts/vendor/qcom/dsi-panel-l11r-38-08-0a-dsc-cmd.dtsi
  sed -i 's/qcom,mdss-pan-physical-height-dimension = <155>;$/qcom,mdss-pan-physical-height-dimension = <1546>;/' arch/arm64/boot/dts/vendor/qcom/dsi-panel-l11r-38-08-0a-dsc-cmd.dtsi
fi

# Kernel compilation
echo "🔨 Starting kernel compilation for $ROM_TYPE..."
make "$KERNEL_DEFCONFIG" O="$OUT_DIR" CC=clang
make -j$(nproc --all) O="$OUT_DIR" CC=clang ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- NM=llvm-nm OBJDUMP=llvm-objdump STRIP=llvm-strip

# Optional KPM patch
if [[ "$kpm" == "true" ]]; then
  echo "🔧 Patching KPM for $ROM_TYPE..."
  cd "$ZIMAGE_DIR"  || exit 1
  curl -LSs "https://github.com/SukiSU-Ultra/SukiSU_KernelPatch_patch/releases/download/0.12.0/patch_linux" -o patch
  chmod +x patch
  ./patch
  gzip -c oImage > Image.gz
  cd "$DIR"
fi

# Artifact preparation
echo "📦 Preparing $ROM_TYPE artifacts..."
mkdir -p "$ARTIFACT_DIR"
cp -fp "$ZIMAGE_DIR/Image.gz" "$ARTIFACT_DIR"
cp -fp "$ZIMAGE_DIR/dtbo.img" "$ARTIFACT_DIR"
cp -fp "$ZIMAGE_DIR/dtb" "$ARTIFACT_DIR"
cp -rp ./anykernel/* "$ARTIFACT_DIR"

for f in Image.gz dtbo.img dtb; do
  if [[ ! -f "$ZIMAGE_DIR/$f" ]]; then
    echo "❌ Missing file: $f"
    exit 1
  fi
done

# Create ZIP
cd "$ARTIFACT_DIR" || exit 1
ZIP_NAME="$ZIP_NAME_BASE-${ROM_TYPE^^}-Unofficial-$TIME.zip"
echo "📦 Creating ZIP: $ZIP_NAME"
zip -r "$ZIP_NAME" *

# Set environment variables for upload
echo "ZIP_NAME_${ROM_TYPE^^}_${KERNEL_BRANCH//-/_}=$ZIP_NAME" >> "$GITHUB_ENV"
echo "ZIP_PATH_${ROM_TYPE^^}_${KERNEL_BRANCH//-/_}=Kernel/$ARTIFACT_DIR/$ZIP_NAME" >> "$GITHUB_ENV"

cd $DIR

# Build done
BUILD_END=$(date +"%s")
DIFF=$((BUILD_END - BUILD_START))
echo "✅ $ROM_TYPE build completed in $((DIFF / 60)) minute(s) and $((DIFF % 60)) seconds"
