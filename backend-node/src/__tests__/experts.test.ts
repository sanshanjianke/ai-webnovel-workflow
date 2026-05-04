// 专家单元测试
import { describe, it, expect, beforeEach } from 'vitest';
import { 
  SeniorAuthor, ReaderRepresentative, PlotArchitect,
  CharacterDesigner, WebEditor, ChapterSplitter, DiscussionSummarizer,
  createExpert, listExperts
} from '../experts';
import { ExpertRole, Granularity } from '../protocols';
import { MockLLM, setLLM, resetLLM } from '../services/llm';

describe('专家系统', () => {
  beforeEach(() => {
    setLLM(new MockLLM('测试响应'));
  });

  describe('专家注册', () => {
    it('应该列出所有专家', () => {
      const experts = listExperts();
      expect(experts).toContain('senior_author_v1');
      expect(experts).toContain('reader_representative_v1');
      expect(experts).toContain('plot_architect_v1');
      expect(experts).toContain('character_designer_v1');
      expect(experts).toContain('web_editor_v1');
      expect(experts).toContain('chapter_splitter_v1');
      expect(experts).toContain('discussion_summarizer_v1');
    });

    it('应该创建专家实例', () => {
      const expert = createExpert('senior_author_v1', ExpertRole.MAIN, Granularity.CHAPTER);
      expect(expert).toBeInstanceOf(SeniorAuthor);
      expect(expert.expertId).toBe('senior_author_v1');
      expect(expert.expertType).toBe('资深作者');
    });

    it('不存在的专家应该抛出错误', () => {
      expect(() => createExpert('nonexistent', ExpertRole.MAIN, Granularity.CHAPTER))
        .toThrow('Expert not found');
    });
  });

  describe('资深作者', () => {
    it('应该生成发言', async () => {
      const expert = new SeniorAuthor(ExpertRole.MAIN, Granularity.CHAPTER);
      const opinion = await expert.speak({
        vision: { coreIdea: '测试故事' }
      });
      
      expect(opinion.expertId).toBe('senior_author_v1');
      expect(opinion.expertType).toBe('资深作者');
      expect(opinion.content).toBeTruthy();
    });

    it('应该支持流式发言', async () => {
      const expert = new SeniorAuthor(ExpertRole.MAIN, Granularity.CHAPTER);
      const chunks: string[] = [];
      let finalOpinion = null;
      
      for await (const chunk of expert.speakStream({})) {
        if (chunk.type === '__done__') {
          finalOpinion = chunk.opinion;
        } else {
          chunks.push(chunk.content);
        }
      }
      
      expect(chunks.length).toBeGreaterThan(0);
      expect(finalOpinion).toBeTruthy();
    });
  });

  describe('读者代表', () => {
    it('应该生成读者视角的发言', async () => {
      const expert = new ReaderRepresentative(ExpertRole.REVIEW, Granularity.CHAPTER);
      const opinion = await expert.speak({
        vision: { coreIdea: '测试故事' }
      });
      
      expect(opinion.expertType).toBe('读者代表');
    });
  });

  describe('剧情架构师', () => {
    it('应该分析故事结构', async () => {
      const expert = new PlotArchitect(ExpertRole.MAIN, Granularity.CHAPTER);
      const opinion = await expert.speak({
        vision: { coreIdea: '测试故事' }
      });
      
      expect(opinion.expertType).toBe('剧情架构师');
    });
  });

  describe('不同粒度', () => {
    it('卷级粒度应该有不同的提示', async () => {
      const expert = new SeniorAuthor(ExpertRole.MAIN, Granularity.VOLUME);
      const opinion = await expert.speak({});
      
      expect(opinion.content).toBeTruthy();
    });

    it('场景级粒度应该有不同的提示', async () => {
      const expert = new SeniorAuthor(ExpertRole.MAIN, Granularity.SCENE);
      const opinion = await expert.speak({});
      
      expect(opinion.content).toBeTruthy();
    });
  });

  describe('不同角色', () => {
    it('主导角色应该有不同的提示', async () => {
      const expert = new SeniorAuthor(ExpertRole.MAIN, Granularity.CHAPTER);
      const opinion = await expert.speak({});
      
      expect(opinion.role).toBe(ExpertRole.MAIN);
    });

    it('审核角色应该有不同的提示', async () => {
      const expert = new SeniorAuthor(ExpertRole.REVIEW, Granularity.CHAPTER);
      const opinion = await expert.speak({});
      
      expect(opinion.role).toBe(ExpertRole.REVIEW);
    });
  });
});
