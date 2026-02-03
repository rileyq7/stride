'use client';

import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Activity, Dribbble, CheckCircle, Star, Users } from 'lucide-react';

export default function Home() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-background to-muted">
      {/* Header */}
      <header className="container mx-auto px-4 py-6">
        <nav className="flex items-center justify-between">
          <div className="text-2xl font-bold">ShoeMatcher</div>
          <div className="flex gap-4">
            <Link href="/quiz/running">
              <Button variant="ghost">Running</Button>
            </Link>
            <Link href="/quiz/basketball">
              <Button variant="ghost">Basketball</Button>
            </Link>
          </div>
        </nav>
      </header>

      {/* Hero Section */}
      <section className="container mx-auto px-4 py-20 text-center">
        <h1 className="text-5xl md:text-6xl font-bold tracking-tight mb-6">
          Find Your Perfect Shoe
        </h1>
        <p className="text-xl text-muted-foreground mb-10 max-w-2xl mx-auto">
          60-second quiz. 500+ shoes analyzed. Zero bias. Get personalized recommendations
          based on AI-parsed reviews and your unique needs.
        </p>

        {/* Category Cards */}
        <div className="grid md:grid-cols-2 gap-6 max-w-3xl mx-auto">
          <Link href="/quiz/running">
            <Card className="hover:shadow-lg transition-shadow cursor-pointer group">
              <CardContent className="p-8">
                <div className="w-16 h-16 bg-primary/10 rounded-full flex items-center justify-center mx-auto mb-4 group-hover:bg-primary/20 transition-colors">
                  <Activity className="w-8 h-8 text-primary" />
                </div>
                <h2 className="text-2xl font-semibold mb-2">Running Shoes</h2>
                <p className="text-muted-foreground">
                  Road, trail, track & more. Find your perfect stride.
                </p>
                <Button className="mt-6 w-full">Start Running Quiz</Button>
              </CardContent>
            </Card>
          </Link>

          <Link href="/quiz/basketball">
            <Card className="hover:shadow-lg transition-shadow cursor-pointer group">
              <CardContent className="p-8">
                <div className="w-16 h-16 bg-primary/10 rounded-full flex items-center justify-center mx-auto mb-4 group-hover:bg-primary/20 transition-colors">
                  <Dribbble className="w-8 h-8 text-primary" />
                </div>
                <h2 className="text-2xl font-semibold mb-2">Basketball Shoes</h2>
                <p className="text-muted-foreground">
                  Indoor, outdoor, all positions. Dominate the court.
                </p>
                <Button className="mt-6 w-full">Start Basketball Quiz</Button>
              </CardContent>
            </Card>
          </Link>
        </div>
      </section>

      {/* Trust Bar */}
      <section className="container mx-auto px-4 py-16">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-8 max-w-4xl mx-auto text-center">
          <div>
            <div className="text-4xl font-bold text-primary">500+</div>
            <div className="text-muted-foreground mt-1">Shoes Analyzed</div>
          </div>
          <div>
            <div className="text-4xl font-bold text-primary">10K+</div>
            <div className="text-muted-foreground mt-1">Reviews Processed</div>
          </div>
          <div>
            <div className="text-4xl font-bold text-primary">95%</div>
            <div className="text-muted-foreground mt-1">Match Satisfaction</div>
          </div>
          <div>
            <div className="text-4xl font-bold text-primary">60s</div>
            <div className="text-muted-foreground mt-1">Quiz Duration</div>
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section className="container mx-auto px-4 py-16 bg-muted/50">
        <h2 className="text-3xl font-bold text-center mb-12">How It Works</h2>
        <div className="grid md:grid-cols-3 gap-8 max-w-4xl mx-auto">
          <div className="text-center">
            <div className="w-12 h-12 bg-primary text-primary-foreground rounded-full flex items-center justify-center mx-auto mb-4 text-xl font-bold">
              1
            </div>
            <h3 className="text-xl font-semibold mb-2">Take the Quiz</h3>
            <p className="text-muted-foreground">
              Answer a few questions about your feet, preferences, and how you plan to use your shoes.
            </p>
          </div>
          <div className="text-center">
            <div className="w-12 h-12 bg-primary text-primary-foreground rounded-full flex items-center justify-center mx-auto mb-4 text-xl font-bold">
              2
            </div>
            <h3 className="text-xl font-semibold mb-2">Get Matched</h3>
            <p className="text-muted-foreground">
              Our AI analyzes thousands of reviews to find shoes that fit your unique profile.
            </p>
          </div>
          <div className="text-center">
            <div className="w-12 h-12 bg-primary text-primary-foreground rounded-full flex items-center justify-center mx-auto mb-4 text-xl font-bold">
              3
            </div>
            <h3 className="text-xl font-semibold mb-2">Shop with Confidence</h3>
            <p className="text-muted-foreground">
              Compare prices across retailers and buy from wherever offers the best deal.
            </p>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="container mx-auto px-4 py-16">
        <h2 className="text-3xl font-bold text-center mb-12">Why ShoeMatcher?</h2>
        <div className="grid md:grid-cols-3 gap-8 max-w-5xl mx-auto">
          <Card>
            <CardContent className="p-6">
              <CheckCircle className="w-10 h-10 text-green-500 mb-4" />
              <h3 className="text-xl font-semibold mb-2">Unbiased Recommendations</h3>
              <p className="text-muted-foreground">
                We&apos;re not tied to any retailer. Our only goal is finding the perfect shoe for you.
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-6">
              <Star className="w-10 h-10 text-yellow-500 mb-4" />
              <h3 className="text-xl font-semibold mb-2">AI-Parsed Reviews</h3>
              <p className="text-muted-foreground">
                We extract real fit data from thousands of reviews to understand how each shoe actually fits.
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-6">
              <Users className="w-10 h-10 text-blue-500 mb-4" />
              <h3 className="text-xl font-semibold mb-2">Expert-Refined</h3>
              <p className="text-muted-foreground">
                Our algorithm is continuously improved by shoe fitting experts through feedback.
              </p>
            </CardContent>
          </Card>
        </div>
      </section>

      {/* CTA */}
      <section className="container mx-auto px-4 py-20 text-center">
        <h2 className="text-3xl font-bold mb-4">Ready to Find Your Match?</h2>
        <p className="text-muted-foreground mb-8 max-w-xl mx-auto">
          Join thousands of runners and ballers who&apos;ve found their perfect shoe. It only takes 60 seconds.
        </p>
        <div className="flex gap-4 justify-center">
          <Link href="/quiz/running">
            <Button size="lg">Running Quiz</Button>
          </Link>
          <Link href="/quiz/basketball">
            <Button size="lg" variant="outline">Basketball Quiz</Button>
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t py-8">
        <div className="container mx-auto px-4 text-center text-muted-foreground">
          <p>&copy; {new Date().getFullYear()} ShoeMatcher. All rights reserved.</p>
        </div>
      </footer>
    </div>
  );
}
