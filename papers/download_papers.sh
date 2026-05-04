#!/bin/bash
# 论文下载脚本 — 下载 arxiv_papers 和 published_papers 中的 PDF
# git clone 默认不包含论文 PDF（.gitignore 已排除），需要的运行此脚本
# 注意：总量约 2GB，需要稳定的网络

echo "此脚本将下载约 2GB 论文 PDF，继续？[y/N]"
read -r answer
[[ "$answer" != "y" && "$answer" != "Y" ]] && exit 0

PAPERS_DIR="$(cd "$(dirname "$0")" && pwd)"

# arxiv papers — 从 arxiv.org 下载
download_arxiv() {
    local arxiv_id="$1"
    local filename="$2"
    local url="https://arxiv.org/pdf/${arxiv_id}"
    echo "下载 $filename ..."
    curl -L -o "${PAPERS_DIR}/arxiv_papers/${filename}" "$url" --silent --show-error
}

# 7 篇核心论文
download_arxiv "2602.15851" "narrative_theory_survey.pdf"
download_arxiv "2603.07155" "narrativeloom.pdf"
download_arxiv "2506.14159" "storysage.pdf"
download_arxiv "2603.05890" "constory_bench.pdf"
download_arxiv "2604.03136" "storyscope.pdf"
download_arxiv "2604.09854" "spoiler_alert.pdf"
download_arxiv "2603.02366" "playwrite.pdf"

echo "arxiv 核心论文下载完成"

# published papers 需要手动获取，此处仅提示
echo ""
echo "published_papers/ 中的论文需从各出版社网站手动下载"
echo "参考 papers/published_papers/README.md 和 books_to_acquire.md"
