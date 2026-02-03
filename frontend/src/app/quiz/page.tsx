'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';

interface Category {
  id: string;
  name: string;
  slug: string;
  is_active: boolean;
}

export default function QuizPage() {
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchCategories = async () => {
      try {
        const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/v1'}/categories`);
        if (res.ok) {
          const data = await res.json();
          setCategories(data.filter((c: Category) => c.is_active));
        }
      } catch (error) {
        console.error('Failed to fetch categories:', error);
        // Fallback categories
        setCategories([
          { id: '1', name: 'Running', slug: 'running', is_active: true },
          { id: '2', name: 'Basketball', slug: 'basketball', is_active: true },
        ]);
      } finally {
        setLoading(false);
      }
    };

    fetchCategories();
  }, []);

  const categoryIcons: Record<string, string> = {
    running: '/running-icon.svg',
    basketball: '/basketball-icon.svg',
  };

  const categoryDescriptions: Record<string, string> = {
    running: 'Find your perfect running shoe based on terrain, distance, and foot type',
    basketball: 'Discover the ideal basketball shoe for your position and play style',
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-background to-muted/20">
      <div className="container mx-auto px-4 py-16">
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold mb-4">Find Your Perfect Shoe</h1>
          <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
            Take our quick quiz to get personalized shoe recommendations based on your needs, preferences, and foot characteristics.
          </p>
        </div>

        {loading ? (
          <div className="grid md:grid-cols-2 gap-6 max-w-3xl mx-auto">
            <Skeleton className="h-48" />
            <Skeleton className="h-48" />
          </div>
        ) : (
          <div className="grid md:grid-cols-2 gap-6 max-w-3xl mx-auto">
            {categories.map((category) => (
              <Card key={category.id} className="hover:shadow-lg transition-shadow">
                <CardHeader>
                  <CardTitle className="text-2xl capitalize">{category.name}</CardTitle>
                  <CardDescription>
                    {categoryDescriptions[category.slug] || `Find the best ${category.name.toLowerCase()} shoes for you`}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <Link href={`/quiz/${category.slug}`}>
                    <Button className="w-full" size="lg">
                      Start {category.name} Quiz
                    </Button>
                  </Link>
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        <div className="text-center mt-12 text-muted-foreground">
          <p>Takes about 2 minutes to complete</p>
        </div>
      </div>
    </div>
  );
}
