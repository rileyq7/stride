'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { useQuizStore } from '@/store/quiz-store';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import {
  Trophy,
  ExternalLink,
  ThumbsUp,
  ThumbsDown,
  RotateCcw,
  CheckCircle,
  AlertCircle,
  Loader2,
} from 'lucide-react';
import { cn } from '@/lib/utils';

export default function ResultsPage() {
  const params = useParams();
  const sessionId = params.sessionId as string;

  const { recommendations, recommendationId, category, reset } = useQuizStore();
  const [feedbackSubmitted, setFeedbackSubmitted] = useState(false);
  const [feedbackLoading, setFeedbackLoading] = useState(false);

  const handleFeedback = async (helpful: boolean) => {
    if (!recommendationId || feedbackSubmitted) return;

    setFeedbackLoading(true);
    try {
      await api.submitFeedback(recommendationId, { helpful });
      setFeedbackSubmitted(true);
    } catch (error) {
      console.error('Failed to submit feedback:', error);
    } finally {
      setFeedbackLoading(false);
    }
  };

  const handleRetake = () => {
    reset();
  };

  if (recommendations.length === 0) {
    return (
      <div className="min-h-screen flex items-center justify-center p-4">
        <Card className="max-w-md w-full">
          <CardContent className="p-8 text-center">
            <AlertCircle className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
            <h2 className="text-xl font-semibold mb-2">No Results Found</h2>
            <p className="text-muted-foreground mb-6">
              It looks like you haven&apos;t completed the quiz yet.
            </p>
            <Link href="/">
              <Button>Start New Quiz</Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    );
  }

  const topMatch = recommendations[0];
  const runnerUps = recommendations.slice(1);

  return (
    <div className="min-h-screen bg-gradient-to-b from-background to-muted">
      {/* Header */}
      <header className="container mx-auto px-4 py-6">
        <nav className="flex items-center justify-between">
          <Link href="/" className="text-2xl font-bold">
            ShoeMatcher
          </Link>
          <Badge variant="secondary" className="capitalize">
            {category} Results
          </Badge>
        </nav>
      </header>

      {/* Results */}
      <main className="container mx-auto px-4 pb-20">
        <div className="max-w-4xl mx-auto">
          {/* Title */}
          <div className="text-center mb-10">
            <h1 className="text-4xl font-bold mb-2">Your Top Matches</h1>
            <p className="text-muted-foreground">
              Based on your {category} profile and preferences
            </p>
          </div>

          {/* Top Match */}
          <Card className="mb-8 border-2 border-primary">
            <CardHeader className="bg-primary/5">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-primary rounded-full flex items-center justify-center">
                  <Trophy className="w-5 h-5 text-primary-foreground" />
                </div>
                <div>
                  <CardTitle className="text-xl">Top Match</CardTitle>
                  <p className="text-sm text-muted-foreground">
                    {Math.round(topMatch.match_score * 100)}% match score
                  </p>
                </div>
              </div>
            </CardHeader>
            <CardContent className="p-6">
              <div className="grid md:grid-cols-[200px_1fr] gap-6">
                {/* Image placeholder */}
                <div className="aspect-square bg-muted rounded-lg flex items-center justify-center">
                  {topMatch.shoe.primary_image_url ? (
                    <img
                      src={topMatch.shoe.primary_image_url}
                      alt={topMatch.shoe.name}
                      className="w-full h-full object-cover rounded-lg"
                    />
                  ) : (
                    <span className="text-4xl">👟</span>
                  )}
                </div>

                {/* Details */}
                <div>
                  <h2 className="text-2xl font-bold mb-1">
                    {topMatch.shoe.brand} {topMatch.shoe.name}
                  </h2>
                  <div className="flex items-center gap-3 mb-4">
                    {topMatch.shoe.current_price_min ? (
                      <span className="text-2xl font-bold text-primary">
                        ${topMatch.shoe.current_price_min}
                      </span>
                    ) : topMatch.shoe.msrp_usd ? (
                      <span className="text-2xl font-bold text-primary">
                        ${topMatch.shoe.msrp_usd}
                      </span>
                    ) : null}
                    {topMatch.shoe.msrp_usd && topMatch.shoe.current_price_min &&
                     topMatch.shoe.current_price_min < topMatch.shoe.msrp_usd && (
                      <span className="text-muted-foreground line-through">
                        ${topMatch.shoe.msrp_usd}
                      </span>
                    )}
                  </div>

                  {/* Reasoning */}
                  <p className="text-muted-foreground mb-4">{topMatch.reasoning}</p>

                  {/* Fit Notes */}
                  <div className="grid grid-cols-2 gap-4 mb-4">
                    {topMatch.fit_notes.sizing && (
                      <div className="text-sm">
                        <span className="font-medium">Sizing:</span>{' '}
                        {topMatch.fit_notes.sizing}
                      </div>
                    )}
                    {topMatch.fit_notes.width && (
                      <div className="text-sm">
                        <span className="font-medium">Width:</span>{' '}
                        {topMatch.fit_notes.width}
                      </div>
                    )}
                  </div>

                  {/* Highlights */}
                  {topMatch.fit_notes.highlights.length > 0 && (
                    <div className="flex flex-wrap gap-2 mb-4">
                      {topMatch.fit_notes.highlights.map((highlight, i) => (
                        <Badge key={i} variant="secondary" className="flex items-center gap-1">
                          <CheckCircle className="w-3 h-3" />
                          {highlight}
                        </Badge>
                      ))}
                    </div>
                  )}

                  {/* Considerations */}
                  {topMatch.fit_notes.considerations.length > 0 && (
                    <div className="text-sm text-muted-foreground mb-4">
                      <span className="font-medium">Consider:</span>{' '}
                      {topMatch.fit_notes.considerations.join(' • ')}
                    </div>
                  )}

                  {/* Affiliate Links */}
                  {topMatch.affiliate_links.length > 0 && (
                    <div className="flex flex-wrap gap-2">
                      {topMatch.affiliate_links.map((link) => (
                        <a
                          key={link.retailer}
                          href={link.url}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          <Button variant="outline" size="sm">
                            {link.retailer}
                            {link.price && ` - $${link.price}`}
                            <ExternalLink className="w-3 h-3 ml-2" />
                          </Button>
                        </a>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Runner Ups */}
          {runnerUps.length > 0 && (
            <>
              <h2 className="text-2xl font-bold mb-4">Also Great Options</h2>
              <div className="grid gap-4 mb-8">
                {runnerUps.map((rec) => (
                  <Card key={rec.shoe.id}>
                    <CardContent className="p-4">
                      <div className="flex gap-4">
                        {/* Image placeholder */}
                        <div className="w-24 h-24 bg-muted rounded-lg flex-shrink-0 flex items-center justify-center">
                          {rec.shoe.primary_image_url ? (
                            <img
                              src={rec.shoe.primary_image_url}
                              alt={rec.shoe.name}
                              className="w-full h-full object-cover rounded-lg"
                            />
                          ) : (
                            <span className="text-2xl">👟</span>
                          )}
                        </div>

                        {/* Details */}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-start justify-between gap-2 mb-1">
                            <h3 className="font-semibold truncate">
                              {rec.shoe.brand} {rec.shoe.name}
                            </h3>
                            <Badge variant="outline">
                              #{rec.rank}
                            </Badge>
                          </div>
                          <div className="flex items-center gap-2 mb-2">
                            <span className="font-bold">
                              ${rec.shoe.current_price_min || rec.shoe.msrp_usd}
                            </span>
                            <span className="text-sm text-muted-foreground">
                              {Math.round(rec.match_score * 100)}% match
                            </span>
                          </div>
                          <p className="text-sm text-muted-foreground line-clamp-2">
                            {rec.reasoning}
                          </p>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </>
          )}

          <Separator className="my-8" />

          {/* Feedback */}
          <Card>
            <CardContent className="p-6">
              {feedbackSubmitted ? (
                <div className="text-center">
                  <CheckCircle className="w-8 h-8 text-green-500 mx-auto mb-2" />
                  <p className="font-medium">Thanks for your feedback!</p>
                  <p className="text-sm text-muted-foreground">
                    This helps us improve our recommendations.
                  </p>
                </div>
              ) : (
                <div className="text-center">
                  <p className="font-medium mb-4">Were these recommendations helpful?</p>
                  <div className="flex justify-center gap-4">
                    <Button
                      variant="outline"
                      onClick={() => handleFeedback(true)}
                      disabled={feedbackLoading}
                    >
                      {feedbackLoading ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <>
                          <ThumbsUp className="w-4 h-4 mr-2" />
                          Yes, helpful!
                        </>
                      )}
                    </Button>
                    <Button
                      variant="outline"
                      onClick={() => handleFeedback(false)}
                      disabled={feedbackLoading}
                    >
                      {feedbackLoading ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <>
                          <ThumbsDown className="w-4 h-4 mr-2" />
                          Not quite
                        </>
                      )}
                    </Button>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Retake */}
          <div className="text-center mt-8">
            <Link href={`/quiz/${category}`} onClick={handleRetake}>
              <Button variant="outline">
                <RotateCcw className="w-4 h-4 mr-2" />
                Retake Quiz
              </Button>
            </Link>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t py-8">
        <div className="container mx-auto px-4 text-center text-muted-foreground">
          <p>&copy; {new Date().getFullYear()} ShoeMatcher. All rights reserved.</p>
        </div>
      </footer>
    </div>
  );
}
