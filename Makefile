ROOT := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
export PYTHONPATH := $(ROOT)packages:$(ROOT)

.PHONY: install install-models setup-demo api worker web check dev night-batch export-demo rebuild-index \
	install-desktop launch build-web release-pack release-pack-windows release-pack-all convert-detect-onnx \
	windows-installer clean-build models-zip

install:
	pip install -r requirements.txt
	cd apps/web && npm install

install-models:
	bash scripts/install_models.sh

models-zip:
	BONEMET_VERSION=$${BONEMET_VERSION:-0.2.0} bash scripts/build_models_zip.sh

convert-detect-onnx:
	python scripts/convert_detect_pt_to_onnx.py --pt "$$BONEMET_DETECT_PT" --out data/models/detect/v1/model.onnx --imgsz 1280 --opset 12

# Windows：生成 Setup.exe（安装器）+ 可选 Nuitka 编译入口
# 说明见 installer/windows/
windows-installer:
	@echo "Windows installer build must run on Windows."
	@echo "Steps:"
	@echo "  1) (optional) BONEMET_DETECT_PT=... make convert-detect-onnx"
	@echo "  2) make release-pack-windows"
	@echo "  3) In Windows: installer\\windows\\build_installer.ps1 -Version $(BONEMET_VERSION)"

clean-build:
	bash scripts/clean_build_artifacts.sh

setup-demo:
	python scripts/setup_demo.py

api:
	@if [ "$${BONEMET_RELOAD:-0}" = "1" ]; then \
		uvicorn apps.api.main:app --reload --host "$${BONEMET_HOST:-0.0.0.0}" --port "$${BONEMET_PORT:-10120}"; \
	else \
		echo "$${BONEMET_PORT:-10120}" > data/logs/bonemet.port 2>/dev/null || true; \
		uvicorn apps.api.main:app --host "$${BONEMET_HOST:-0.0.0.0}" --port "$${BONEMET_PORT:-10120}"; \
	fi

worker:
	bash scripts/run_worker.sh

worker-local:
	python -m apps.worker.main

web:
	cd apps/web && VITE_HOST=$${VITE_HOST:-0.0.0.0} VITE_API_HOST=$${VITE_API_HOST:-127.0.0.1} VITE_API_PORT=$${VITE_API_PORT:-10120} npm run dev:poll

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
	@echo "Terminal 3: make web  → http://localhost:5173"

# 一键安装 / 启动（单端口 8080，API + 网页）
install-desktop:
	bash scripts/install-desktop.sh

launch:
	bash scripts/launch.sh

build-web:
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
