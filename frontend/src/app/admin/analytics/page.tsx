'use client';

import { useEffect, useState } from 'react';
import { adminApi } from '@/lib/admin-api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { useToast } from '@/hooks/use-toast';
import {
  BarChart3,
  Users,
  MousePointerClick,
  CheckCircle,
  MessageSquare,
  RefreshCw,
  TrendingUp,
} from 'lucide-react';

interface Analytics {
  quizzes_completed: number;
  recommendations_generated: number;
  click_through_rate: number;
  quiz_completion_rate: number;
  feedback_summary: Record<string, unknown>;
  top_recommended_shoes: Array<{ shoe_id: string; name: string; count: number }>;
}

export default function AnalyticsPage() {
  const { toast } = useToast();
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [period, setPeriod] = useState('30d');

  useEffect(() => {
    loadAnalytics();
  }, [period]);

  const loadAnalytics = async () => {
    setLoading(true);
    try {
      const data = await adminApi.getAnalytics(period);
      setAnalytics(data);
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to load analytics',
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  };

  const formatPercent = (value: number) => {
    return `${(value * 100).toFixed(1)}%`;
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-32" />
          ))}
        </div>
        <Skeleton className="h-64" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Analytics Dashboard</h1>
        <div className="flex items-center gap-3">
          <Select value={period} onValueChange={setPeriod}>
            <SelectTrigger className="w-32">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="7d">Last 7 days</SelectItem>
              <SelectItem value="30d">Last 30 days</SelectItem>
              <SelectItem value="90d">Last 90 days</SelectItem>
            </SelectContent>
          </Select>
          <Button onClick={loadAnalytics} variant="outline" size="sm">
            <RefreshCw className="w-4 h-4 mr-2" />
            Refresh
          </Button>
        </div>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Quizzes Completed</p>
                <p className="text-3xl font-bold">{analytics?.quizzes_completed || 0}</p>
              </div>
              <div className="p-3 bg-blue-100 rounded-full">
                <Users className="w-6 h-6 text-blue-600" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Recommendations Generated</p>
                <p className="text-3xl font-bold">{analytics?.recommendations_generated || 0}</p>
              </div>
              <div className="p-3 bg-green-100 rounded-full">
                <CheckCircle className="w-6 h-6 text-green-600" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Click-Through Rate</p>
                <p className="text-3xl font-bold">{formatPercent(analytics?.click_through_rate || 0)}</p>
              </div>
              <div className="p-3 bg-purple-100 rounded-full">
                <MousePointerClick className="w-6 h-6 text-purple-600" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Quiz Completion Rate</p>
                <p className="text-3xl font-bold">{formatPercent(analytics?.quiz_completion_rate || 0)}</p>
              </div>
              <div className="p-3 bg-orange-100 rounded-full">
                <TrendingUp className="w-6 h-6 text-orange-600" />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Top Recommended Shoes */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <BarChart3 className="w-5 h-5" />
            Top Recommended Shoes
          </CardTitle>
          <CardDescription>
            Most frequently recommended shoes in the selected period
          </CardDescription>
        </CardHeader>
        <CardContent>
          {analytics?.top_recommended_shoes && analytics.top_recommended_shoes.length > 0 ? (
            <div className="space-y-3">
              {analytics.top_recommended_shoes.map((shoe, index) => (
                <div
                  key={shoe.shoe_id}
                  className="flex items-center justify-between p-3 bg-muted rounded-lg"
                >
                  <div className="flex items-center gap-3">
                    <span className="font-bold text-primary">#{index + 1}</span>
                    <span>{shoe.name}</span>
                  </div>
                  <span className="text-muted-foreground">{shoe.count} recommendations</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8 text-muted-foreground">
              No recommendation data available for this period.
            </div>
          )}
        </CardContent>
      </Card>

      {/* Feedback Summary */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <MessageSquare className="w-5 h-5" />
            User Feedback
          </CardTitle>
          <CardDescription>
            Summary of user feedback on recommendations
          </CardDescription>
        </CardHeader>
        <CardContent>
          {analytics?.feedback_summary && Object.keys(analytics.feedback_summary).length > 0 ? (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {Object.entries(analytics.feedback_summary).map(([key, value]) => (
                <div key={key} className="p-4 bg-muted rounded-lg text-center">
                  <p className="text-2xl font-bold">{String(value)}</p>
                  <p className="text-sm text-muted-foreground capitalize">
                    {key.replace(/_/g, ' ')}
                  </p>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8 text-muted-foreground">
              No feedback data available for this period.
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
