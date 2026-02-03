'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { adminApi } from '@/lib/admin-api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Skeleton } from '@/components/ui/skeleton';
import { useToast } from '@/hooks/use-toast';
import { Plus, Search, AlertCircle, CheckCircle, Edit } from 'lucide-react';

interface Shoe {
  id: string;
  brand: string;
  name: string;
  category: string;
  is_active: boolean;
  needs_review: boolean;
  last_scraped_at: string | null;
  is_complete: boolean;
}

export default function ShoesPage() {
  const { toast } = useToast();
  const [shoes, setShoes] = useState<Shoe[]>([]);
  const [loading, setLoading] = useState(true);
  const [categoryFilter, setCategoryFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    loadShoes();
  }, [categoryFilter, statusFilter]);

  const loadShoes = async () => {
    setLoading(true);
    try {
      const params: { category?: string; needs_review?: boolean; incomplete?: boolean } = {};
      if (categoryFilter !== 'all') {
        params.category = categoryFilter;
      }
      if (statusFilter === 'needs_review') {
        params.needs_review = true;
      } else if (statusFilter === 'incomplete') {
        params.incomplete = true;
      }
      const data = await adminApi.getShoes(params);
      setShoes(data);
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to load shoes',
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  };

  const filteredShoes = shoes.filter((shoe) => {
    if (!searchQuery) return true;
    const query = searchQuery.toLowerCase();
    return (
      shoe.name.toLowerCase().includes(query) ||
      shoe.brand.toLowerCase().includes(query)
    );
  });

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-3xl font-bold">Shoes</h1>
        <Button>
          <Plus className="w-4 h-4 mr-2" />
          Add Shoe
        </Button>
      </div>

      {/* Filters */}
      <Card className="mb-6">
        <CardContent className="p-4">
          <div className="flex gap-4">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search shoes..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10"
              />
            </div>
            <Select value={categoryFilter} onValueChange={setCategoryFilter}>
              <SelectTrigger className="w-40">
                <SelectValue placeholder="Category" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Categories</SelectItem>
                <SelectItem value="running">Running</SelectItem>
                <SelectItem value="basketball">Basketball</SelectItem>
              </SelectContent>
            </Select>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-48">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Shoes</SelectItem>
                <SelectItem value="incomplete">Missing Data</SelectItem>
                <SelectItem value="needs_review">Needs Review</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Table */}
      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Brand</TableHead>
                <TableHead>Name</TableHead>
                <TableHead>Category</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Last Scraped</TableHead>
                <TableHead className="w-20"></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? (
                Array.from({ length: 5 }).map((_, i) => (
                  <TableRow key={i}>
                    <TableCell><Skeleton className="h-4 w-20" /></TableCell>
                    <TableCell><Skeleton className="h-4 w-32" /></TableCell>
                    <TableCell><Skeleton className="h-4 w-16" /></TableCell>
                    <TableCell><Skeleton className="h-4 w-16" /></TableCell>
                    <TableCell><Skeleton className="h-4 w-24" /></TableCell>
                    <TableCell><Skeleton className="h-8 w-8" /></TableCell>
                  </TableRow>
                ))
              ) : filteredShoes.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                    No shoes found
                  </TableCell>
                </TableRow>
              ) : (
                filteredShoes.map((shoe) => (
                  <TableRow key={shoe.id}>
                    <TableCell className="font-medium">{shoe.brand}</TableCell>
                    <TableCell>{shoe.name}</TableCell>
                    <TableCell>
                      <Badge variant="outline" className="capitalize">
                        {shoe.category}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        {shoe.is_complete ? (
                          <CheckCircle className="w-4 h-4 text-green-500" />
                        ) : (
                          <AlertCircle className="w-4 h-4 text-yellow-500" />
                        )}
                        {!shoe.is_complete && (
                          <Badge variant="outline" className="text-xs text-yellow-600 border-yellow-300">
                            Incomplete
                          </Badge>
                        )}
                        {shoe.needs_review && (
                          <Badge variant="secondary" className="text-xs">
                            Review
                          </Badge>
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="text-muted-foreground text-sm">
                      {shoe.last_scraped_at
                        ? new Date(shoe.last_scraped_at).toLocaleDateString()
                        : 'Never'}
                    </TableCell>
                    <TableCell>
                      <Link href={`/admin/shoes/${shoe.id}`}>
                        <Button variant="ghost" size="icon">
                          <Edit className="h-4 w-4" />
                        </Button>
                      </Link>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
