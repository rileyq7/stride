'use client';

import { useEffect, useState } from 'react';
import { adminApi } from '@/lib/admin-api';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { useToast } from '@/hooks/use-toast';
import { Bot, Play, RefreshCw, Clock, CheckCircle, XCircle, Loader2 } from 'lucide-react';

interface ScrapeJob {
  id: string;
  job_type: string;
  target_id: string | null;
  status: string;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
  created_at: string;
}

interface Brand {
  id: string;
  name: string;
  slug: string;
}

export default function ScraperPage() {
  const { toast } = useToast();
  const [jobs, setJobs] = useState<ScrapeJob[]>([]);
  const [brands, setBrands] = useState<Brand[]>([]);
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState(false);

  // Scrape form state
  const [jobType, setJobType] = useState<'single_shoe' | 'brand' | 'category' | 'all_reviews'>('brand');
  const [targetBrand, setTargetBrand] = useState<string>('');

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [jobsData, brandsData] = await Promise.all([
        adminApi.getScrapeJobs(),
        adminApi.getBrands(),
      ]);
      setJobs(jobsData);
      setBrands(brandsData);
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to load scraper data',
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  };

  const triggerScrape = async () => {
    if (jobType === 'brand' && !targetBrand) {
      toast({
        title: 'Error',
        description: 'Please select a brand',
        variant: 'destructive',
      });
      return;
    }

    setTriggering(true);
    try {
      const result = await adminApi.triggerScrape({
        job_type: jobType,
        target_id: jobType === 'brand' ? targetBrand : undefined,
      });
      toast({
        title: 'Scrape Job Started',
        description: `Job ${result.job_id.slice(0, 8)} started. Estimated time: ${result.estimated_duration_minutes} min`,
      });
      loadData();
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to start scrape job',
        variant: 'destructive',
      });
    } finally {
      setTriggering(false);
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="w-4 h-4 text-green-500" />;
      case 'failed':
        return <XCircle className="w-4 h-4 text-red-500" />;
      case 'running':
        return <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />;
      default:
        return <Clock className="w-4 h-4 text-yellow-500" />;
    }
  };

  const getStatusBadge = (status: string) => {
    const colors: Record<string, string> = {
      pending: 'bg-yellow-100 text-yellow-800',
      running: 'bg-blue-100 text-blue-800',
      completed: 'bg-green-100 text-green-800',
      failed: 'bg-red-100 text-red-800',
    };
    return (
      <Badge className={colors[status] || 'bg-gray-100 text-gray-800'}>
        {status}
      </Badge>
    );
  };

  const formatJobType = (type: string) => {
    return type.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase());
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-48 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Scraper Management</h1>
        <Button onClick={loadData} variant="outline" size="sm">
          <RefreshCw className="w-4 h-4 mr-2" />
          Refresh
        </Button>
      </div>

      {/* Trigger New Scrape */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Bot className="w-5 h-5" />
            Trigger New Scrape
          </CardTitle>
          <CardDescription>
            Start a new scraping job to collect shoe data from brand websites
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-4 items-end">
            <div className="space-y-2">
              <label className="text-sm font-medium">Job Type</label>
              <Select value={jobType} onValueChange={(v) => setJobType(v as typeof jobType)}>
                <SelectTrigger className="w-48">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="brand">Scrape Brand</SelectItem>
                  <SelectItem value="category">Scrape Category</SelectItem>
                  <SelectItem value="all_reviews">Scrape All Reviews</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {jobType === 'brand' && (
              <div className="space-y-2">
                <label className="text-sm font-medium">Select Brand</label>
                <Select value={targetBrand} onValueChange={setTargetBrand}>
                  <SelectTrigger className="w-48">
                    <SelectValue placeholder="Choose brand..." />
                  </SelectTrigger>
                  <SelectContent>
                    {brands.map((brand) => (
                      <SelectItem key={brand.id} value={brand.id}>
                        {brand.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}

            <Button onClick={triggerScrape} disabled={triggering}>
              {triggering ? (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <Play className="w-4 h-4 mr-2" />
              )}
              Start Scrape
            </Button>
          </div>

          <div className="mt-4 p-4 bg-muted rounded-lg text-sm text-muted-foreground">
            <p><strong>Note:</strong> Web scraping requires the backend scraper service to be running.
            Jobs are queued and processed asynchronously. Check job status below.</p>
          </div>
        </CardContent>
      </Card>

      {/* Job History */}
      <Card>
        <CardHeader>
          <CardTitle>Scrape Job History</CardTitle>
          <CardDescription>
            Recent scraping jobs and their status
          </CardDescription>
        </CardHeader>
        <CardContent>
          {jobs.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              No scrape jobs found. Start a new scrape above.
            </div>
          ) : (
            <div className="space-y-3">
              {jobs.map((job) => (
                <div
                  key={job.id}
                  className="flex items-center justify-between p-4 border rounded-lg"
                >
                  <div className="flex items-center gap-4">
                    {getStatusIcon(job.status)}
                    <div>
                      <div className="font-medium">{formatJobType(job.job_type)}</div>
                      <div className="text-sm text-muted-foreground">
                        {job.target_id ? `Target: ${job.target_id.slice(0, 8)}` : 'All targets'}
                        {' '}&middot;{' '}
                        {new Date(job.created_at).toLocaleString()}
                      </div>
                      {job.error_message && (
                        <div className="text-sm text-red-500 mt-1">
                          Error: {job.error_message}
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    {getStatusBadge(job.status)}
                    {job.completed_at && (
                      <span className="text-sm text-muted-foreground">
                        Completed: {new Date(job.completed_at).toLocaleTimeString()}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
