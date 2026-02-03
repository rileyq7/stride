const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/v1';

export interface Question {
  id: string;
  type: 'single_select' | 'multi_select' | 'rank' | 'shoe_history';
  question: string;
  hint?: string;
  options: QuestionOption[];
  optional?: boolean;
  max_select?: number;
  max_rank?: number;
}

export interface QuestionOption {
  value: string;
  label: string;
  icon?: string;
  description?: string;
}

export interface QuizStartResponse {
  session_id: string;
  session_token: string;
  questions: Question[];
}

export interface QuizAnswerResponse {
  next_question: Question | null;
  progress: number;
  is_complete: boolean;
}

export interface ShoeInfo {
  id: string;
  brand: string;
  name: string;
  primary_image_url: string | null;
  msrp_usd: number | null;
  current_price_min: number | null;
}

export interface FitNotes {
  sizing: string | null;
  width: string | null;
  highlights: string[];
  considerations: string[];
}

export interface AffiliateLink {
  retailer: string;
  url: string;
  price: number | null;
}

export interface RecommendedShoe {
  rank: number;
  shoe: ShoeInfo;
  match_score: number;
  reasoning: string;
  fit_notes: FitNotes;
  affiliate_links: AffiliateLink[];
}

export interface RecommendResponse {
  recommendation_id: string;
  shoes: RecommendedShoe[];
  not_recommended: Array<{
    shoe: ShoeInfo;
    reason: string;
  }>;
}

export interface ShoeDetail {
  id: string;
  brand: {
    id: string;
    name: string;
    logo_url: string | null;
  };
  category: string;
  name: string;
  full_name: string;
  slug: string;
  model_year: number | null;
  version: string | null;
  specs: Record<string, unknown> | null;
  fit_profile: {
    size_runs: string | null;
    width_runs: string | null;
    toe_box_room: string | null;
    arch_support: string | null;
    break_in_period: string | null;
    durability_rating: string | null;
    expected_miles_min: number | null;
    expected_miles_max: number | null;
    common_complaints: string[] | null;
    works_well_for: string[] | null;
    overall_sentiment: number | null;
    review_count: number | null;
  } | null;
  pricing: {
    msrp_usd: number | null;
    current_min: number | null;
    current_max: number | null;
  };
  affiliate_links: AffiliateLink[];
  images: string[];
}

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `API error: ${response.status}`);
    }

    return response.json();
  }

  // Quiz endpoints
  async startQuiz(category: string, region?: string): Promise<QuizStartResponse> {
    return this.request('/quiz/start', {
      method: 'POST',
      body: JSON.stringify({ category, region }),
    });
  }

  async submitAnswer(
    sessionId: string,
    questionId: string,
    answer: unknown
  ): Promise<QuizAnswerResponse> {
    return this.request(`/quiz/${sessionId}/answer`, {
      method: 'POST',
      body: JSON.stringify({ question_id: questionId, answer }),
    });
  }

  async getRecommendations(
    sessionId: string,
    previousShoes?: Array<{ shoe_id?: string; name?: string; liked: boolean; notes?: string }>
  ): Promise<RecommendResponse> {
    return this.request(`/quiz/${sessionId}/recommend`, {
      method: 'POST',
      body: JSON.stringify({ previous_shoes: previousShoes }),
    });
  }

  async submitFeedback(
    recommendationId: string,
    feedback: {
      helpful: boolean;
      purchased_shoe_id?: string;
      rating?: number;
      notes?: string;
    }
  ): Promise<{ success: boolean }> {
    return this.request(`/recommendations/${recommendationId}/feedback`, {
      method: 'POST',
      body: JSON.stringify(feedback),
    });
  }

  // Shoe endpoints
  async getShoes(params?: {
    category?: string;
    brand?: string;
    limit?: number;
    offset?: number;
  }): Promise<ShoeInfo[]> {
    const searchParams = new URLSearchParams();
    if (params?.category) searchParams.set('category', params.category);
    if (params?.brand) searchParams.set('brand', params.brand);
    if (params?.limit) searchParams.set('limit', params.limit.toString());
    if (params?.offset) searchParams.set('offset', params.offset.toString());

    const query = searchParams.toString();
    return this.request(`/shoes${query ? `?${query}` : ''}`);
  }

  async getShoe(shoeId: string): Promise<ShoeDetail> {
    return this.request(`/shoes/${shoeId}`);
  }
}

export const api = new ApiClient();
