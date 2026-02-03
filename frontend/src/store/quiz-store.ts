import { create } from 'zustand';
import { api, Question, RecommendedShoe } from '@/lib/api';

interface PreviousShoe {
  shoe_id?: string;
  name?: string;
  liked: boolean;
  notes?: string;
}

interface QuizState {
  // Session
  sessionId: string | null;
  sessionToken: string | null;
  category: 'running' | 'basketball' | null;

  // Questions
  questions: Question[];
  currentQuestionIndex: number;
  answers: Record<string, unknown>;

  // Previous shoes (optional step)
  previousShoes: PreviousShoe[];

  // Status
  isLoading: boolean;
  error: string | null;
  isComplete: boolean;

  // Results
  recommendationId: string | null;
  recommendations: RecommendedShoe[];

  // Actions
  startQuiz: (category: 'running' | 'basketball') => Promise<void>;
  submitAnswer: (questionId: string, answer: unknown) => Promise<void>;
  goBack: () => void;
  addPreviousShoe: (shoe: PreviousShoe) => void;
  removePreviousShoe: (index: number) => void;
  getRecommendations: () => Promise<void>;
  reset: () => void;
}

const initialState = {
  sessionId: null,
  sessionToken: null,
  category: null,
  questions: [],
  currentQuestionIndex: 0,
  answers: {},
  previousShoes: [],
  isLoading: false,
  error: null,
  isComplete: false,
  recommendationId: null,
  recommendations: [],
};

export const useQuizStore = create<QuizState>((set, get) => ({
  ...initialState,

  startQuiz: async (category) => {
    set({ isLoading: true, error: null });

    try {
      const response = await api.startQuiz(category);

      set({
        sessionId: response.session_id,
        sessionToken: response.session_token,
        category,
        questions: response.questions,
        currentQuestionIndex: 0,
        answers: {},
        isLoading: false,
        isComplete: false,
      });
    } catch (error) {
      set({
        isLoading: false,
        error: error instanceof Error ? error.message : 'Failed to start quiz',
      });
    }
  },

  submitAnswer: async (questionId, answer) => {
    const { sessionId, questions, currentQuestionIndex, answers } = get();

    if (!sessionId) {
      set({ error: 'No active quiz session' });
      return;
    }

    set({ isLoading: true, error: null });

    try {
      const response = await api.submitAnswer(sessionId, questionId, answer);

      const newAnswers = { ...answers, [questionId]: answer };

      set({
        answers: newAnswers,
        currentQuestionIndex: currentQuestionIndex + 1,
        isComplete: response.is_complete,
        isLoading: false,
      });
    } catch (error) {
      set({
        isLoading: false,
        error: error instanceof Error ? error.message : 'Failed to submit answer',
      });
    }
  },

  goBack: () => {
    const { currentQuestionIndex } = get();
    if (currentQuestionIndex > 0) {
      set({ currentQuestionIndex: currentQuestionIndex - 1 });
    }
  },

  addPreviousShoe: (shoe) => {
    const { previousShoes } = get();
    set({ previousShoes: [...previousShoes, shoe] });
  },

  removePreviousShoe: (index) => {
    const { previousShoes } = get();
    set({
      previousShoes: previousShoes.filter((_, i) => i !== index),
    });
  },

  getRecommendations: async () => {
    const { sessionId, previousShoes } = get();

    if (!sessionId) {
      set({ error: 'No active quiz session' });
      return;
    }

    set({ isLoading: true, error: null });

    try {
      const response = await api.getRecommendations(
        sessionId,
        previousShoes.length > 0 ? previousShoes : undefined
      );

      set({
        recommendationId: response.recommendation_id,
        recommendations: response.shoes,
        isLoading: false,
      });
    } catch (error) {
      set({
        isLoading: false,
        error: error instanceof Error ? error.message : 'Failed to get recommendations',
      });
    }
  },

  reset: () => {
    set(initialState);
  },
}));
