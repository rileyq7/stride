const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/v1';

class AdminApiClient {
  private baseUrl: string;
  private token: string | null = null;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
    if (typeof window !== 'undefined') {
      this.token = localStorage.getItem('admin_token');
    }
  }

  setToken(token: string) {
    this.token = token;
    if (typeof window !== 'undefined') {
      localStorage.setItem('admin_token', token);
    }
  }

  clearToken() {
    this.token = null;
    if (typeof window !== 'undefined') {
      localStorage.removeItem('admin_token');
    }
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };

    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }

    const response = await fetch(url, {
      ...options,
      headers: {
        ...headers,
        ...options.headers,
      },
    });

    if (response.status === 401) {
      this.clearToken();
      if (typeof window !== 'undefined') {
        window.location.href = '/admin/login';
      }
      throw new Error('Unauthorized');
    }

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `API error: ${response.status}`);
    }

    return response.json();
  }

  // Auth
  async login(email: string, password: string): Promise<{ access_token: string }> {
    const response = await this.request<{ access_token: string }>('/admin/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    this.setToken(response.access_token);
    return response;
  }

  async getCurrentUser(): Promise<{
    id: string;
    email: string;
    name: string | null;
    role: string;
  }> {
    return this.request('/admin/me');
  }

  // Recommendations
  async getRecommendations(params?: {
    status?: string;
    category?: string;
    page?: number;
    limit?: number;
  }): Promise<{
    items: Array<{
      id: string;
      created_at: string;
      quiz_summary: Record<string, unknown>;
      recommended_shoes: Array<{
        rank: number;
        shoe_id: string;
        shoe_name: string;
        score: number;
      }>;
      review_status: string;
    }>;
    total: number;
    page: number;
  }> {
    const searchParams = new URLSearchParams();
    if (params?.status) searchParams.set('status', params.status);
    if (params?.category) searchParams.set('category', params.category);
    if (params?.page) searchParams.set('page', params.page.toString());
    if (params?.limit) searchParams.set('limit', params.limit.toString());

    const query = searchParams.toString();
    return this.request(`/admin/recommendations${query ? `?${query}` : ''}`);
  }

  async reviewRecommendation(
    id: string,
    data: {
      status: 'approved' | 'rejected' | 'adjusted';
      adjusted_shoes?: Array<{ shoe_id: string; rank: number }>;
      notes?: string;
    }
  ): Promise<{ success: boolean; training_example_created: boolean }> {
    return this.request(`/admin/recommendations/${id}/review`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  // Shoes
  async getShoe(id: string): Promise<{
    id: string;
    brand_id: string;
    brand: string;
    brand_slug: string;
    category_id: string;
    category: string;
    name: string;
    slug: string;
    model_year: number | null;
    version: string | null;
    msrp_usd: number | null;
    current_price_min: number | null;
    current_price_max: number | null;
    available_regions: string[] | null;
    width_options: string[] | null;
    is_discontinued: boolean;
    is_active: boolean;
    needs_review: boolean;
    primary_image_url: string | null;
    image_urls: string[] | null;
    last_scraped_at: string | null;
    running_attributes: {
      weight_oz: number | null;
      stack_height_heel_mm: number | null;
      stack_height_forefoot_mm: number | null;
      drop_mm: number | null;
      terrain: string | null;
      subcategory: string | null;
      has_carbon_plate: boolean | null;
      has_rocker: boolean | null;
      cushion_type: string | null;
      cushion_level: string | null;
      best_for_distances: string[] | null;
      best_for_pace: string | null;
    } | null;
    basketball_attributes: {
      weight_oz: number | null;
      cut: string | null;
      court_type: string | null;
      cushion_type: string | null;
      cushion_level: string | null;
      traction_pattern: string | null;
      ankle_support_level: string | null;
      lockdown_level: string | null;
      best_for_position: string[] | null;
      best_for_playstyle: string[] | null;
    } | null;
    fit_profile: {
      size_runs: string | null;
      size_offset: number | null;
      width_runs: string | null;
      toe_box_room: string | null;
      heel_fit: string | null;
      midfoot_fit: string | null;
      arch_support: string | null;
      arch_support_level: string | null;
      break_in_period: string | null;
      break_in_miles: number | null;
      all_day_comfort: boolean | null;
      expected_miles_min: number | null;
      expected_miles_max: number | null;
      durability_rating: string | null;
      common_wear_points: string[] | null;
      common_complaints: string[] | null;
      works_well_for: string[] | null;
      avoid_if: string[] | null;
    } | null;
  }> {
    return this.request(`/admin/shoes/${id}`);
  }

  async getShoes(params?: {
    category?: string;
    brand?: string;
    needs_review?: boolean;
    incomplete?: boolean;
    limit?: number;
    offset?: number;
  }): Promise<Array<{
    id: string;
    brand: string;
    name: string;
    category: string;
    is_active: boolean;
    needs_review: boolean;
    last_scraped_at: string | null;
    is_complete: boolean;
  }>> {
    const searchParams = new URLSearchParams();
    if (params?.category) searchParams.set('category', params.category);
    if (params?.brand) searchParams.set('brand', params.brand);
    if (params?.needs_review !== undefined) searchParams.set('needs_review', params.needs_review.toString());
    if (params?.incomplete !== undefined) searchParams.set('incomplete', params.incomplete.toString());
    if (params?.limit) searchParams.set('limit', params.limit.toString());
    if (params?.offset) searchParams.set('offset', params.offset.toString());

    const query = searchParams.toString();
    return this.request(`/admin/shoes${query ? `?${query}` : ''}`);
  }

  async createShoe(data: {
    brand_id: string;
    category_id: string;
    name: string;
    slug: string;
    [key: string]: unknown;
  }): Promise<{ id: string; name: string }> {
    return this.request('/admin/shoes', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updateShoe(
    id: string,
    data: Record<string, unknown>
  ): Promise<{ success: boolean }> {
    return this.request(`/admin/shoes/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async deleteShoe(id: string): Promise<{ success: boolean }> {
    return this.request(`/admin/shoes/${id}`, {
      method: 'DELETE',
    });
  }

  async updateFitProfile(
    shoeId: string,
    data: Record<string, unknown>
  ): Promise<{ success: boolean }> {
    return this.request(`/admin/shoes/${shoeId}/fit-profile`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  // Scraper
  async triggerScrape(data: {
    job_type: 'single_shoe' | 'brand' | 'category' | 'all_reviews';
    target_id?: string;
    sources?: string[];
  }): Promise<{ job_id: string; status: string; estimated_duration_minutes: number }> {
    return this.request('/admin/scrape/trigger', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getScrapeJobs(status?: string): Promise<Array<{
    id: string;
    job_type: string;
    target_id: string | null;
    status: string;
    started_at: string | null;
    completed_at: string | null;
    error_message: string | null;
    created_at: string;
  }>> {
    const query = status ? `?status=${status}` : '';
    return this.request(`/admin/scrape/jobs${query}`);
  }

  // Analytics
  async getAnalytics(period: string = '30d'): Promise<{
    quizzes_completed: number;
    recommendations_generated: number;
    click_through_rate: number;
    quiz_completion_rate: number;
    feedback_summary: Record<string, unknown>;
    top_recommended_shoes: Array<{ shoe_id: string; name: string; count: number }>;
  }> {
    return this.request(`/admin/analytics/overview?period=${period}`);
  }

  // Brands & Categories
  async getBrands(): Promise<Array<{ id: string; name: string; slug: string }>> {
    return this.request('/admin/brands');
  }

  async getCategories(): Promise<Array<{ id: string; name: string; slug: string; is_active: boolean }>> {
    return this.request('/admin/categories');
  }
}

export const adminApi = new AdminApiClient();
