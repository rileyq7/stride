'use client';

import { useEffect, useState } from 'react';
import { adminApi } from '@/lib/admin-api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { ClipboardCheck, Footprints, TrendingUp, Users } from 'lucide-react';

interface Analytics {
  quizzes_completed: number;
  recommendations_generated: number;
  click_through_rate: number;
  quiz_completion_rate: number;
}

export default function AdminDashboard() {
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [pendingReviews, setPendingReviews] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadData = async () => {
      try {
        const [analyticsData, recsData] = await Promise.all([
          adminApi.getAnalytics('30d'),
          adminApi.getRecommendations({ status: 'pending', limit: 1 }),
        ]);
        setAnalytics(analyticsData);
        setPendingReviews(recsData.total);
      } catch (error) {
        console.error('Failed to load dashboard data:', error);
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, []);

  const stats = [
    {
      title: 'Quizzes Completed',
      value: analytics?.quizzes_completed ?? 0,
      icon: Users,
      description: 'Last 30 days',
    },
    {
      title: 'Recommendations',
      value: analytics?.recommendations_generated ?? 0,
      icon: Footprints,
      description: 'Last 30 days',
    },
    {
      title: 'Click-through Rate',
      value: `${((analytics?.click_through_rate ?? 0) * 100).toFixed(1)}%`,
      icon: TrendingUp,
      description: 'Affiliate clicks',
    },
    {
      title: 'Pending Reviews',
      value: pendingReviews,
      icon: ClipboardCheck,
      description: 'Awaiting approval',
    },
  ];

  return (
    <div>
      <h1 className="text-3xl font-bold mb-8">Dashboard</h1>

      {/* Stats Grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4 mb-8">
        {stats.map((stat, i) => (
          <Card key={i}>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                {stat.title}
              </CardTitle>
              <stat.icon className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              {loading ? (
                <Skeleton className="h-8 w-20" />
              ) : (
                <>
                  <div className="text-2xl font-bold">{stat.value}</div>
                  <p className="text-xs text-muted-foreground">{stat.description}</p>
                </>
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Quick Actions */}
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Quick Actions</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <a
              href="/admin/recommendations"
              className="block p-4 rounded-lg border hover:bg-muted transition-colors"
            >
              <div className="font-medium">Review Recommendations</div>
              <div className="text-sm text-muted-foreground">
                {pendingReviews} pending reviews
              </div>
            </a>
            <a
              href="/admin/shoes"
              className="block p-4 rounded-lg border hover:bg-muted transition-colors"
            >
              <div className="font-medium">Manage Shoes</div>
              <div className="text-sm text-muted-foreground">
                Add, edit, or update shoe data
              </div>
            </a>
            <a
              href="/admin/scraper"
              className="block p-4 rounded-lg border hover:bg-muted transition-colors"
            >
              <div className="font-medium">Run Scraper</div>
              <div className="text-sm text-muted-foreground">
                Fetch new reviews and prices
              </div>
            </a>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>System Status</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between">
              <span>API Server</span>
              <span className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-green-500"></span>
                Healthy
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span>Database</span>
              <span className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-green-500"></span>
                Connected
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span>Scraper Workers</span>
              <span className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-yellow-500"></span>
                Idle
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span>AI Service</span>
              <span className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-green-500"></span>
                Available
              </span>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
