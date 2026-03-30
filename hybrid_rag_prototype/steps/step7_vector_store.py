"""
步骤7：向量存储

功能：将切片向量化并存入Chroma向量数据库

用法：
    python steps/step7_vector_store.py --input output/06_slices --output output/07_vector_db
"""

import json
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from openai import OpenAI

import os
EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY", "")
EMBEDDING_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
EMBEDDING_MODEL = "text-embedding-v3"

try:
    import chromadb
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False
    print("警告: chromadb未安装，请运行: pip install chromadb")


class EmbeddingClient:
    """Embedding客户端"""
    
    def __init__(self):
        self.client = OpenAI(
            api_key=EMBEDDING_API_KEY,
            base_url=EMBEDDING_BASE_URL
        )
        self.model = EMBEDDING_MODEL
    
    def embed(self, texts: list, batch_size: int = 10) -> list:
        """批量生成embedding（分批处理）"""
        if not texts:
            return []
        
        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            response = self.client.embeddings.create(
                model=self.model,
                input=batch
            )
            all_embeddings.extend([item.embedding for item in response.data])
        
        return all_embeddings


class VectorStore:
    """向量存储"""
    
    def __init__(self, db_path: Path):
        if not CHROMA_AVAILABLE:
            raise ImportError("chromadb未安装")
        
        self.client = chromadb.PersistentClient(path=str(db_path))
        self.collections = {}
        self.embedding_client = EmbeddingClient()
    
    def get_collection(self, dimension: str):
        """获取或创建collection"""
        if dimension not in self.collections:
            self.collections[dimension] = self.client.get_or_create_collection(
                name=f"slices_{dimension}",
                metadata={"dimension": dimension}
            )
        return self.collections[dimension]
    
    def add_slices(self, dimension: str, slices: list):
        """添加切片到向量库"""
        collection = self.get_collection(dimension)
        
        # 准备数据
        ids = []
        documents = []
        metadatas = []
        
        for s in slices:
            ids.append(s['id'])
            # 检索文本 = search_text（已包含多视角改写）
            doc_parts = [s.get('search_text', '')]
            
            # 添加完整内容的前500字（补充关键信息）
            if s.get('full_content'):
                doc_parts.append(s['full_content'][:500])
            
            documents.append("\n".join(doc_parts))
            
            # 元数据
            meta = {
                "name": s['name'],
                "dimension": dimension,
            }
            # 标签转字符串存储
            for k, v in s.get('tags', {}).items():
                if isinstance(v, list):
                    meta[k] = ",".join(v)
                else:
                    meta[k] = str(v)
            metadatas.append(meta)
        
        # 生成embedding
        print(f"  生成embedding ({len(documents)}条)...")
        embeddings = self.embedding_client.embed(documents)
        
        # 存入向量库
        collection.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas
        )
        
        return len(ids)
    
    def search(self, query: str, dimension: str = None, k: int = 5) -> list:
        """搜索"""
        query_embedding = self.embedding_client.embed([query])[0]
        
        if dimension:
            collection = self.get_collection(dimension)
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=k
            )
        else:
            # 搜索所有维度
            all_results = []
            for dim, collection in self.collections.items():
                results = collection.query(
                    query_embeddings=[query_embedding],
                    n_results=k
                )
                for i, id in enumerate(results['ids'][0]):
                    all_results.append({
                        "id": id,
                        "document": results['documents'][0][i],
                        "metadata": results['metadatas'][0][i],
                        "distance": results['distances'][0][i] if results.get('distances') else 0,
                        "dimension": dim
                    })
            # 按距离排序
            all_results.sort(key=lambda x: x['distance'])
            return all_results[:k]
        
        # 转换结果
        results_list = []
        for i, id in enumerate(results['ids'][0]):
            results_list.append({
                "id": id,
                "document": results['documents'][0][i],
                "metadata": results['metadatas'][0][i],
                "distance": results['distances'][0][i] if results.get('distances') else 0
            })
        
        return results_list


def load_slices(input_dir: Path) -> dict:
    """加载切片"""
    slices = {}
    
    for dim_dir in input_dir.iterdir():
        if dim_dir.is_dir():
            dim = dim_dir.name
            slices[dim] = []
            
            for md_file in dim_dir.glob("*.md"):
                # 从MD文件解析
                content = md_file.read_text(encoding='utf-8')
                
                # 解析元数据
                lines = content.split('\n')
                name = lines[0].replace('# ', '') if lines else ''
                
                # 解析标签
                tags = {}
                for line in lines:
                    if line.startswith('**标签**:'):
                        tags_str = line.split('**:')[1].strip()
                        try:
                            tags = json.loads(tags_str)
                        except:
                            pass
                
                # 解析检索文本（包含多视角改写）
                search_text = ""
                in_search = False
                for line in lines:
                    if '## 检索文本' in line:
                        in_search = True
                        continue
                    if in_search and line.startswith('##'):
                        break
                    if in_search:
                        search_text += line + "\n"
                
                # 解析完整内容
                full_content = ""
                in_content = False
                for line in lines:
                    if '## 完整内容' in line:
                        in_content = True
                        continue
                    if in_content:
                        full_content += line + "\n"
                
                # 解析问题
                questions = []
                in_questions = False
                for line in lines:
                    if '## 附加问题' in line:
                        in_questions = True
                        continue
                    if in_questions and line.startswith('##'):
                        break
                    if in_questions and line.startswith('- '):
                        questions.append(line[2:])
                
                slices[dim].append({
                    "id": md_file.stem,
                    "name": name,
                    "search_text": search_text.strip(),
                    "full_content": full_content.strip(),
                    "tags": tags,
                    "questions": questions
                })
    
    return slices


def main():
    parser = argparse.ArgumentParser(description='步骤7：向量存储')
    parser.add_argument('--input', '-i', default='output/06_slices')
    parser.add_argument('--output', '-o', default='output/07_vector_db')
    args = parser.parse_args()
    
    print("\n" + "="*60)
    print("步骤7：向量存储")
    print("="*60)
    
    if not CHROMA_AVAILABLE:
        print("✗ chromadb未安装")
        return
    
    input_dir = Path(args.input)
    if not input_dir.exists():
        print(f"✗ 输入目录不存在: {input_dir}")
        return
    
    # 加载切片
    print(f"\n加载切片: {input_dir}")
    slices = load_slices(input_dir)
    
    total = sum(len(v) for v in slices.values())
    print(f"  共 {total} 个切片")
    for dim, slice_list in slices.items():
        print(f"  - {dim}: {len(slice_list)}个")
    
    # 初始化向量库
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n初始化向量库: {output_dir}")
    store = VectorStore(output_dir)
    
    # 存储各维度
    print(f"\n存储向量...")
    for dim, slice_list in slices.items():
        count = store.add_slices(dim, slice_list)
        print(f"  {dim}: {count}条")
    
    # 测试搜索
    print(f"\n测试搜索...")
    test_queries = [
        "李白的穿越经历",
        "打脸爽点",
        "铺垫功能"
    ]
    
    for query in test_queries:
        print(f"\n查询: {query}")
        results = store.search(query, k=3)
        for r in results:
            print(f"  - [{r.get('dimension', 'unknown')}] {r['metadata'].get('name', r['id'])} (距离: {r.get('distance', 0):.4f})")
    
    print(f"\n✓ 向量库保存到: {output_dir}")


if __name__ == "__main__":
    main()