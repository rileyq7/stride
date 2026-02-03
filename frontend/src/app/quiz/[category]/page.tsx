'use client';

import { useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { useQuizStore } from '@/store/quiz-store';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { ArrowLeft, ArrowRight, Loader2, CheckCircle } from 'lucide-react';
import { cn } from '@/lib/utils';

export default function QuizPage() {
  const params = useParams();
  const router = useRouter();
  const category = params.category as 'running' | 'basketball';

  const {
    sessionId,
    questions,
    currentQuestionIndex,
    answers,
    isLoading,
    error,
    isComplete,
    startQuiz,
    submitAnswer,
    goBack,
    getRecommendations,
    recommendations,
    category: storeCategory,
    reset,
  } = useQuizStore();

  // Start quiz on mount or when category changes
  useEffect(() => {
    if (category === 'running' || category === 'basketball') {
      // If no session or category changed, start a new quiz
      if (!sessionId || storeCategory !== category) {
        reset();
        startQuiz(category);
      }
    }
  }, [category, sessionId, storeCategory, startQuiz, reset]);

  // Navigate to results when recommendations are ready
  useEffect(() => {
    if (recommendations.length > 0 && sessionId) {
      router.push(`/results/${sessionId}`);
    }
  }, [recommendations, sessionId, router]);

  // Get recommendations when quiz is complete
  useEffect(() => {
    if (isComplete && !isLoading && recommendations.length === 0) {
      getRecommendations();
    }
  }, [isComplete, isLoading, recommendations.length, getRecommendations]);

  const currentQuestion = questions[currentQuestionIndex];
  const progress = questions.length > 0 ? ((currentQuestionIndex) / questions.length) * 100 : 0;

  const handleOptionSelect = async (value: string) => {
    if (!currentQuestion || isLoading) return;

    if (currentQuestion.type === 'multi_select') {
      const currentAnswer = (answers[currentQuestion.id] as string[]) || [];
      const newAnswer = currentAnswer.includes(value)
        ? currentAnswer.filter((v) => v !== value)
        : [...currentAnswer, value];

      // Check for exclusive options (like "none")
      if (value === 'none') {
        await submitAnswer(currentQuestion.id, ['none']);
      } else if (newAnswer.includes('none')) {
        await submitAnswer(currentQuestion.id, newAnswer.filter((v) => v !== 'none'));
      } else if (currentQuestion.max_select && newAnswer.length > currentQuestion.max_select) {
        return; // Don't exceed max selections
      } else {
        // For multi-select, store locally until user clicks next
        useQuizStore.setState({
          answers: { ...answers, [currentQuestion.id]: newAnswer },
        });
      }
    } else {
      // Single select - submit immediately
      await submitAnswer(currentQuestion.id, value);
    }
  };

  const handleMultiSelectSubmit = async () => {
    if (!currentQuestion || isLoading) return;
    const currentAnswer = answers[currentQuestion.id];
    if (currentAnswer && (currentAnswer as string[]).length > 0) {
      await submitAnswer(currentQuestion.id, currentAnswer);
    }
  };

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center p-4">
        <Card className="max-w-md w-full">
          <CardContent className="p-6 text-center">
            <p className="text-destructive mb-4">{error}</p>
            <Button onClick={() => startQuiz(category)}>Try Again</Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!currentQuestion && !isComplete) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin" />
      </div>
    );
  }

  if (isComplete || isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center p-4">
        <Card className="max-w-md w-full">
          <CardContent className="p-8 text-center">
            <Loader2 className="w-12 h-12 animate-spin mx-auto mb-4" />
            <h2 className="text-xl font-semibold mb-2">Finding Your Perfect Matches</h2>
            <p className="text-muted-foreground">
              Analyzing your profile against hundreds of shoes...
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  const currentAnswer = answers[currentQuestion.id];
  const isMultiSelect = currentQuestion.type === 'multi_select';
  const selectedValues = isMultiSelect ? (currentAnswer as string[]) || [] : [];

  return (
    <div className="min-h-screen bg-gradient-to-b from-background to-muted">
      {/* Header */}
      <header className="container mx-auto px-4 py-6">
        <nav className="flex items-center justify-between">
          <Link href="/" className="text-2xl font-bold">
            ShoeMatcher
          </Link>
          <Badge variant="secondary" className="capitalize">
            {category} Quiz
          </Badge>
        </nav>
      </header>

      {/* Progress */}
      <div className="container mx-auto px-4 mb-8">
        <div className="max-w-2xl mx-auto">
          <div className="flex justify-between text-sm text-muted-foreground mb-2">
            <span>Question {currentQuestionIndex + 1} of {questions.length}</span>
            <span>{Math.round(progress)}% complete</span>
          </div>
          <Progress value={progress} className="h-2" />
        </div>
      </div>

      {/* Question */}
      <main className="container mx-auto px-4 pb-20">
        <div className="max-w-2xl mx-auto">
          <Card>
            <CardHeader>
              <CardTitle className="text-2xl">{currentQuestion.question}</CardTitle>
              {currentQuestion.hint && (
                <p className="text-muted-foreground">{currentQuestion.hint}</p>
              )}
            </CardHeader>
            <CardContent>
              <div className="grid gap-3">
                {currentQuestion.options.map((option) => {
                  const isSelected = isMultiSelect
                    ? selectedValues.includes(option.value)
                    : currentAnswer === option.value;

                  return (
                    <button
                      key={option.value}
                      onClick={() => handleOptionSelect(option.value)}
                      disabled={isLoading}
                      className={cn(
                        'w-full p-4 text-left rounded-lg border-2 transition-all',
                        'hover:border-primary hover:bg-primary/5',
                        isSelected
                          ? 'border-primary bg-primary/10'
                          : 'border-border bg-background',
                        isLoading && 'opacity-50 cursor-not-allowed'
                      )}
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <div className="font-medium">{option.label}</div>
                          {option.description && (
                            <div className="text-sm text-muted-foreground mt-1">
                              {option.description}
                            </div>
                          )}
                        </div>
                        {isSelected && (
                          <CheckCircle className="w-5 h-5 text-primary" />
                        )}
                      </div>
                    </button>
                  );
                })}
              </div>

              {/* Navigation */}
              <div className="flex justify-between mt-8">
                <Button
                  variant="outline"
                  onClick={goBack}
                  disabled={currentQuestionIndex === 0 || isLoading}
                >
                  <ArrowLeft className="w-4 h-4 mr-2" />
                  Back
                </Button>

                {isMultiSelect && (
                  <Button
                    onClick={handleMultiSelectSubmit}
                    disabled={selectedValues.length === 0 || isLoading}
                  >
                    {isLoading ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <>
                        Next
                        <ArrowRight className="w-4 h-4 ml-2" />
                      </>
                    )}
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      </main>
    </div>
  );
}
