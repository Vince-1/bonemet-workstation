ROOT := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
export PYTHONPATH := $(ROOT)packages:$(ROOT)

.PHONY: install install-models setup-demo api worker web check dev night-batch export-demo rebuild-index \
	install-desktop launch build-web export-icon release-pack release-pack-windows release-pack-all convert-detect-onnx \
	windows-installer windows-setup windows-setup-full windows-setup-full-no-models \
	release-pack-windows-no-models clean-build models-zip

BONEMET_VERSION ?= 0.2.0

export-icon:
	python scripts/export_bonemet_icon.py

install:
	pip install -r requirements.txt
	cd apps/web && npm install

install-models:
	bash scripts/install_models.sh

models-zip:
	BONEMET_VERSION=$${BONEMET_VERSION:-0.2.0} bash scripts/build_models_zip.sh

convert-detect-onnx:
	python scripts/convert_detect_pt_to_onnx.py --pt "$$BONEMET_DETECT_PT" --out data/models/detect/model.onnx --imgsz 1280 --opset 12

# Windows：生成 Setup.exe（需 Windows + Inno Setup；ISCC 自动查找，见 installer/windows/_inno.ps1）
# 说明见 docs/PACKAGING.md、installer/windows/README.md
windows-setup:
	powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$(CURDIR)installer/windows/build_installer.ps1" -Version $(BONEMET_VERSION)

windows-setup-full:
	powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$(CURDIR)installer/windows/one_click.ps1" -Version $(BONEMET_VERSION) -BuildReleasePack

windows-setup-full-no-models:
	powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$(CURDIR)installer/windows/one_click.ps1" -Version $(BONEMET_VERSION) -BuildReleasePack -NoModels

release-pack-windows-no-models:
	BUNDLE_MODELS=0 BONEMET_TARGET=windows bash scripts/build-release-pack.sh

windows-installer: windows-setup
	@echo "Alias: use 'make windows-setup' (needs release-pack-windows first) or 'make windows-setup-full'"

clean-build:
	bash scripts/clean_build_artifacts.sh

setup-demo:
	bash -lc 'export PYTHONPATH="$(CURDIR)/packages:$(CURDIR)"; python scripts/setup_demo.py'

api:
	bash scripts/run-api.sh

worker:
	bash scripts/run_worker.sh

worker-local:
	bash scripts/run_worker.sh

web:
	cd apps/web && VITE_USE_POLLING=1 VITE_HOST=$${VITE_HOST:-0.0.0.0} VITE_DEV_PORT=$${VITE_DEV_PORT:-10123} VITE_API_PORT=$${VITE_API_PORT:-10120} npm run dev:poll

check:
	bash scripts/check_no_trains_imports.sh

rebuild-index:
	python scripts/rebuild_case_index.py

night-batch:
	python scripts/night_batch.py

export-demo:
	python scripts/export_approved.py --export-id demo_export --study-uids STUDY_DEMO_001

dev:
	@echo "Terminal 1: make api"
	@echo "Terminal 2: make worker"
	@echo "Terminal 3: make web  → http://localhost:10123"

# 一键安装 / 启动（单端口 8080，API + 网页）
install-desktop:
	bash scripts/install-desktop.sh

launch:
	bash scripts/launch.sh

build-web: export-icon
	cd apps/web && npm install && npm run build

# 生成可交付安装包
# Linux:  dist-release/BoneMet-Workstation-*-linux-x64.tar.gz
# Windows: dist-release/BoneMet-Workstation-*-win-x64.zip
release-pack:
	bash scripts/build-release-pack.sh

release-pack-windows:
	BONEMET_TARGET=windows bash scripts/build-release-pack.sh

release-pack-all:
	BONEMET_TARGET=all bash scripts/build-release-pack.sh
