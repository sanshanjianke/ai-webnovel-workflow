# Related Work: AI-Assisted Web Novel Creation Systems

## 1. Literature Review on arXiv

### 1.1 Search Methodology

Search queries used on arXiv:
- `AI novel writing generation`
- `narrative generation LLM pipeline`
- `creative writing AI multi-agent`

### 1.2 Related Papers Found

| Paper | Year | Core Contribution | Category |
|-------|------|-------------------|----------|
| [Narrative Theory-Driven LLM Methods](https://arxiv.org/abs/2602.15851) | 2026 | Survey on narrative theory + NLP integration; taxonomy of narrative tasks | cs.CL, cs.AI |
| [NarrativeLoom](https://arxiv.org/abs/2603.07155) | 2026 | Multi-persona co-creative system; 50-user study; Campbell's BVSR theory | cs.HC, cs.MA |
| [StorySage](https://arxiv.org/abs/2506.14159) | 2025 | Multi-agent framework for autobiography writing; 28-user study | cs.HC, cs.AI |
| [ConStory-Bench](https://arxiv.org/abs/2603.05890) | 2026 | Benchmark for consistency in long-form story generation; 5 error categories | cs.CL, cs.AI |
| [StoryScope](https://arxiv.org/abs/2604.03136) | 2026 | Narrative feature analysis; AI vs human story detection (93.2% F1) | cs.CL |
| [Spoiler Alert](https://arxiv.org/abs/2604.09854) | 2026 | 100-Endings metric for narrative tension; story generation pipeline | cs.CL |
| [PlayWrite](https://arxiv.org/abs/2603.02366) | 2026 | Multimodal XR system for narrative co-authoring; 13-user study | cs.HC, cs.AI |

### 1.3 Key Findings from Literature

**Narrative Theory-Driven LLM Methods (Survey)**:
- Proposes taxonomy for narrative tasks reflecting narratology distinctions
- Highlights LLMs enable easy connection between NLP pipelines and abstract narrative concepts
- Challenge: No unified benchmark for "narrative quality"

**NarrativeLoom**:
- Multi-persona system grounded in Campbell's Blind Variation and Selective Retention theory
- AI personas generate diverse options (blind variation); users select and refine (selective retention)
- Results: Stories rated higher on all Torrance Test dimensions (fluency, flexibility, originality, elaboration)

**ConStory-Bench**:
- Defines 5 error categories with 19 subtypes for consistency bugs
- Finds errors most common in factual and temporal dimensions
- Errors tend to appear around middle of narratives

---

## 2. Comparative Analysis

### 2.1 Architecture Comparison

| Dimension | Existing Research | Our Approach |
|-----------|------------------|--------------|
| **Target Domain** | General story generation | **Web novels (commercial literature)** |
| **Architecture** | Single-layer or two-layer | **Four-layer waterfall model** |
| **Collaboration Mode** | Multi-agent generating options | **Expert conference + Editor-in-chief decision** |
| **Theoretical Foundation** | General narratology | **Narratology + Web novel commercial theory (dual-database mapping)** |
| **Engineering Rigor** | Limited | **Software engineering mindset (layered decoupling, RAG, vector DB)** |

### 2.2 Detailed Comparison with NarrativeLoom

| Aspect | NarrativeLoom | Our L2 Architecture Layer |
|--------|--------------|---------------------------|
| **Theory** | Campbell's BVSR (blind variation → selective retention) | Expert conference (architect + editor + character designer) |
| **Agent Roles** | Generic AI personas | **Specialized experts with distinct responsibilities** |
| | | - Plot Architect: Sequence/function decomposition |
| | | - Web Editor: Market appeal, pacing, "cool points" |
| | | - Character Designer: Action role assignment, OOC prevention |
| **User Role** | Creative director (select/ refine) | Editor-in-chief (final decision, logic audit) |
| **Iteration** | Single-pass selection | **Multi-round expert discussion (max 3 iterations)** |
| **Domain Knowledge** | General narrative | **Web novel-specific (爽点公式, 黄金三章, 毒点规避)** |

### 2.3 Detailed Comparison with StorySage

| Aspect | StorySage | Our Approach |
|--------|-----------|--------------|
| **Task** | Autobiography writing | **Fiction/web novel creation** |
| **Agents** | Interviewer, Scribe, Planner, Writer, Coordinator | **L1-L4 layered agents** |
| **Memory** | Session-based memory collection | **Shared setting database + state machine** |
| **Output** | Single autobiography document | **Structured pipeline: Vision → Outline → Chapter Plan → Text** |

### 2.4 Our Unique Contributions

1. **Domain-Specific Focus**: First system specifically designed for Chinese web novel creation, incorporating commercial web novel theory (爽点, 节奏, 黄金三章)

2. **Four-Layer Architecture**:
   ```
   L1 Seed Layer     → Story Vision Document
   L2 Architecture   → Refined Story Outline (Expert Conference)
   L3 Narrative      → Chapter Plan (Effect → Technique Mapping)
   L4 Render         → Final Text
   ```

3. **Dual-Database Mapping Mechanism**:
   - Web Novel Theory Database (效果学): "What effect to achieve"
   - Narratology Database (结构学): "How to achieve it technically"
   - Mapping Library: Translates abstract effects to concrete narrative techniques

4. **Expert Conference Protocol**:
   - Three specialized experts with distinct RAG databases
   - Three driving modes: Character-driven / Plot-driven / Market-driven
   - User as Editor-in-chief with final decision authority

5. **Multi-Dimensional Chunking for RAG**:
   - Plot dimension: By sequence/event
   - Character dimension: By character appearance
   - Emotion dimension: By emotional phase
   - Function dimension: By narrative function

---

## 3. arXiv Publication Feasibility

### 3.1 Suitable Categories

arXiv is appropriate for this research. Recommended categories:

| Primary | Secondary | Optional |
|---------|-----------|----------|
| `cs.CL` (Computation and Language) | `cs.AI` (Artificial Intelligence) | `cs.HC` (Human-Computer Interaction) |

### 3.2 Evidence from Existing Papers

All related papers listed above are published on arXiv, confirming this is an accepted research direction:
- NarrativeLoom: cs.HC, cs.MA
- StorySage: cs.HC, cs.AI, cs.MA
- ConStory-Bench: cs.CL, cs.AI

### 3.3 Requirements for Publication

To publish on arXiv, the following should be added:

| Requirement | Current Status | Action Needed |
|-------------|----------------|---------------|
| Theoretical Framework | ✅ Complete | None |
| System Architecture | ✅ Complete | None |
| Implementation | ⚠️ Partial | Complete hybrid_rag_prototype |
| User Study | ❌ Missing | 20-50 participants minimum |
| Quantitative Evaluation | ❌ Missing | Define metrics, run experiments |
| Baseline Comparison | ❌ Missing | Compare with NarrativeLoom, StorySage |
| Open Source Code | ⚠️ Partial | Complete and release GitHub repo |

### 3.4 Suggested Evaluation Metrics

1. **Quality Metrics**:
   - Narrative consistency (adapt ConStory-Bench taxonomy)
   - User satisfaction (Likert scale)
   - Expert rating (Torrance Test dimensions)

2. **Efficiency Metrics**:
   - Time to complete story
   - Number of iterations needed
   - User intervention frequency

3. **Domain-Specific Metrics**:
   - "Cool point" density (爽点密度)
   - Pacing score (节奏评分)
   - Consistency with web novel conventions

---

## 4. Recommended Next Steps

### Short-term (1-2 months)
1. Complete hybrid_rag_prototype implementation
2. Run 3-5 complete case studies (full L1→L4 pipeline)
3. Document all outputs and user feedback

### Medium-term (3-6 months)
1. Design controlled user study (N=30-50)
2. Implement evaluation metrics
3. Compare with baseline methods (NarrativeLoom, zero-shot GPT)

### Long-term (6-12 months)
1. Write full paper for arXiv submission
2. Release open-source code and datasets
3. Consider conference submission (ACL, EMNLP, CHI)

---

## 5. References

1. Liu, D. Y., Joshi, A., & Dawson, P. (2026). Narrative Theory-Driven LLM Methods for Automatic Story Generation and Understanding: A Survey. arXiv:2602.15851.

2. Ma, Y., Peng, Y., Yang, F., et al. (2026). NarrativeLoom: Enhancing Creative Storytelling through Multi-Persona Collaborative Improvisation. arXiv:2603.07155.

3. Talaei, S., Li, M., Grover, K., et al. (2025). StorySage: Conversational Autobiography Writing Powered by a Multi-Agent Framework. arXiv:2506.14159.

4. Li, J., Guo, X., Wu, Y., et al. (2026). Lost in Stories: Consistency Bugs in Long Story Generation by LLMs. arXiv:2603.05890.

5. Russell, J., Rajendhran, R., Pham, C. M., et al. (2026). StoryScope: Investigating idiosyncrasies in AI fiction. arXiv:2604.03136.

6. Sui, P., Zhu, Y., Cheng, T., et al. (2026). Spoiler Alert: Narrative Forecasting as a Metric for Tension in LLM Storytelling. arXiv:2604.09854.

7. Tütüncü, E. K., Zhou, Q., Brudy, F., et al. (2026). PlayWrite: A Multimodal System for AI Supported Narrative Co-Authoring Through Play in XR. arXiv:2603.02366.

---

*Document created: 2026-04-20*
*Last updated: 2026-04-20*
