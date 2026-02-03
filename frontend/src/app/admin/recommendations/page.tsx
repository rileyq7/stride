'use client';

import { useEffect, useState } from 'react';
import { adminApi } from '@/lib/admin-api';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Textarea } from '@/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { useToast } from '@/hooks/use-toast';
import { CheckCircle, XCircle, Edit, Loader2 } from 'lucide-react';

interface Recommendation {
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
}

export default function RecommendationsPage() {
  const { toast } = useToast();
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('pending');
  const [reviewingId, setReviewingId] = useState<string | null>(null);
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState<string | null>(null);

  useEffect(() => {
    loadRecommendations();
  }, [statusFilter]);

  const loadRecommendations = async () => {
    setLoading(true);
    try {
      const data = await adminApi.getRecommendations({ status: statusFilter });
      setRecommendations(data.items);
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to load recommendations',
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  };

  const handleReview = async (id: string, status: 'approved' | 'rejected') => {
    setSubmitting(id);
    try {
      await adminApi.reviewRecommendation(id, {
        status,
        notes: notes[id],
      });
      toast({
        title: 'Success',
        description: `Recommendation ${status}`,
      });
      // Remove from list
      setRecommendations((prev) => prev.filter((r) => r.id !== id));
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to submit review',
        variant: 'destructive',
      });
    } finally {
      setSubmitting(null);
    }
  };

  const formatQuizSummary = (summary: Record<string, unknown>) => {
    const keys = ['terrain', 'distance', 'position', 'court_type', 'priorities', 'foot_issues', 'budget'];
    const items: string[] = [];

    for (const key of keys) {
      if (summary[key]) {
        const value = summary[key];
        if (Array.isArray(value)) {
          items.push(`${key}: ${value.join(', ')}`);
        } else {
          items.push(`${key}: ${value}`);
        }
      }
    }

    return items;
  };

  const statusColors: Record<string, string> = {
    pending: 'bg-yellow-100 text-yellow-800',
    approved: 'bg-green-100 text-green-800',
    rejected: 'bg-red-100 text-red-800',
    adjusted: 'bg-blue-100 text-blue-800',
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-3xl font-bold">Review Queue</h1>
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-40">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="pending">Pending</SelectItem>
            <SelectItem value="approved">Approved</SelectItem>
            <SelectItem value="rejected">Rejected</SelectItem>
            <SelectItem value="adjusted">Adjusted</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {loading ? (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <Card key={i}>
              <CardContent className="p-6">
                <Skeleton className="h-6 w-48 mb-4" />
                <Skeleton className="h-4 w-full mb-2" />
                <Skeleton className="h-4 w-3/4" />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : recommendations.length === 0 ? (
        <Card>
          <CardContent className="p-12 text-center">
            <p className="text-muted-foreground">No {statusFilter} recommendations</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {recommendations.map((rec) => (
            <Card key={rec.id}>
              <CardHeader className="flex flex-row items-center justify-between">
                <div>
                  <CardTitle className="text-lg">
                    Recommendation #{rec.id.slice(0, 8)}
                  </CardTitle>
                  <p className="text-sm text-muted-foreground">
                    {new Date(rec.created_at).toLocaleString()}
                  </p>
                </div>
                <Badge className={statusColors[rec.review_status]}>
                  {rec.review_status}
                </Badge>
              </CardHeader>
              <CardContent>
                {/* Quiz Summary */}
                <div className="mb-4">
                  <h4 className="font-medium mb-2">Quiz Answers</h4>
                  <div className="flex flex-wrap gap-2">
                    {formatQuizSummary(rec.quiz_summary).map((item, i) => (
                      <Badge key={i} variant="secondary">
                        {item}
                      </Badge>
                    ))}
                  </div>
                </div>

                {/* Recommended Shoes */}
                <div className="mb-4">
                  <h4 className="font-medium mb-2">Recommended Shoes</h4>
                  <div className="space-y-2">
                    {(rec.recommended_shoes || []).map((shoe, idx) => (
                      <div
                        key={shoe?.shoe_id || idx}
                        className="flex items-center justify-between p-2 bg-muted rounded"
                      >
                        <div className="flex items-center gap-3">
                          <span className="font-bold text-primary">#{shoe?.rank || idx + 1}</span>
                          <span>{shoe?.shoe_name || (shoe?.shoe_id ? shoe.shoe_id.slice(0, 8) : 'Unknown')}</span>
                        </div>
                        <span className="text-sm text-muted-foreground">
                          {Math.round((shoe?.score || 0) * 100)}% match
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Review Actions */}
                {rec.review_status === 'pending' && (
                  <div className="border-t pt-4 mt-4">
                    {reviewingId === rec.id ? (
                      <div className="space-y-4">
                        <Textarea
                          placeholder="Optional notes..."
                          value={notes[rec.id] || ''}
                          onChange={(e) =>
                            setNotes({ ...notes, [rec.id]: e.target.value })
                          }
                        />
                        <div className="flex gap-2">
                          <Button
                            onClick={() => handleReview(rec.id, 'approved')}
                            disabled={submitting === rec.id}
                            className="bg-green-600 hover:bg-green-700"
                          >
                            {submitting === rec.id ? (
                              <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                              <>
                                <CheckCircle className="w-4 h-4 mr-2" />
                                Approve
                              </>
                            )}
                          </Button>
                          <Button
                            variant="destructive"
                            onClick={() => handleReview(rec.id, 'rejected')}
                            disabled={submitting === rec.id}
                          >
                            {submitting === rec.id ? (
                              <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                              <>
                                <XCircle className="w-4 h-4 mr-2" />
                                Reject
                              </>
                            )}
                          </Button>
                          <Button
                            variant="outline"
                            onClick={() => setReviewingId(null)}
                          >
                            Cancel
                          </Button>
                        </div>
                      </div>
                    ) : (
                      <div className="flex gap-2">
                        <Button
                          onClick={() => handleReview(rec.id, 'approved')}
                          disabled={submitting === rec.id}
                          className="bg-green-600 hover:bg-green-700"
                        >
                          <CheckCircle className="w-4 h-4 mr-2" />
                          Approve
                        </Button>
                        <Button
                          variant="outline"
                          onClick={() => setReviewingId(rec.id)}
                        >
                          <Edit className="w-4 h-4 mr-2" />
                          Review with Notes
                        </Button>
                        <Button
                          variant="destructive"
                          onClick={() => handleReview(rec.id, 'rejected')}
                          disabled={submitting === rec.id}
                        >
                          <XCircle className="w-4 h-4 mr-2" />
                          Reject
                        </Button>
                      </div>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
