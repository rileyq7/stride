'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { adminApi } from '@/lib/admin-api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { Skeleton } from '@/components/ui/skeleton';
import { useToast } from '@/hooks/use-toast';
import { ArrowLeft, Save, AlertTriangle, CheckCircle2 } from 'lucide-react';

type ShoeData = Awaited<ReturnType<typeof adminApi.getShoe>>;

export default function ShoeEditPage() {
  const params = useParams();
  const router = useRouter();
  const { toast } = useToast();
  const shoeId = params.id as string;

  const [shoe, setShoe] = useState<ShoeData | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  // Form state
  const [basicInfo, setBasicInfo] = useState({
    name: '',
    msrp_usd: '',
    is_active: true,
    is_discontinued: false,
  });

  const [runningAttrs, setRunningAttrs] = useState({
    weight_oz: '',
    drop_mm: '',
    stack_height_heel_mm: '',
    stack_height_forefoot_mm: '',
    terrain: '',
    subcategory: '',
    cushion_type: '',
    cushion_level: '',
    has_carbon_plate: false,
    has_rocker: false,
  });

  const [basketballAttrs, setBasketballAttrs] = useState({
    weight_oz: '',
    cut: '',
    court_type: '',
    cushion_type: '',
    cushion_level: '',
    traction_pattern: '',
    ankle_support_level: '',
    lockdown_level: '',
  });

  const [fitProfile, setFitProfile] = useState({
    size_runs: '',
    size_offset: '',
    width_runs: '',
    toe_box_room: '',
    heel_fit: '',
    midfoot_fit: '',
    arch_support: '',
    break_in_period: '',
    expected_miles_min: '',
    expected_miles_max: '',
    durability_rating: '',
  });

  useEffect(() => {
    loadShoe();
  }, [shoeId]);

  const loadShoe = async () => {
    setLoading(true);
    try {
      const data = await adminApi.getShoe(shoeId);
      setShoe(data);

      // Populate basic info
      setBasicInfo({
        name: data.name || '',
        msrp_usd: data.msrp_usd?.toString() || '',
        is_active: data.is_active,
        is_discontinued: data.is_discontinued,
      });

      // Populate running attributes
      if (data.running_attributes) {
        const ra = data.running_attributes;
        setRunningAttrs({
          weight_oz: ra.weight_oz?.toString() || '',
          drop_mm: ra.drop_mm?.toString() || '',
          stack_height_heel_mm: ra.stack_height_heel_mm?.toString() || '',
          stack_height_forefoot_mm: ra.stack_height_forefoot_mm?.toString() || '',
          terrain: ra.terrain || '',
          subcategory: ra.subcategory || '',
          cushion_type: ra.cushion_type || '',
          cushion_level: ra.cushion_level || '',
          has_carbon_plate: ra.has_carbon_plate || false,
          has_rocker: ra.has_rocker || false,
        });
      }

      // Populate basketball attributes
      if (data.basketball_attributes) {
        const ba = data.basketball_attributes;
        setBasketballAttrs({
          weight_oz: ba.weight_oz?.toString() || '',
          cut: ba.cut || '',
          court_type: ba.court_type || '',
          cushion_type: ba.cushion_type || '',
          cushion_level: ba.cushion_level || '',
          traction_pattern: ba.traction_pattern || '',
          ankle_support_level: ba.ankle_support_level || '',
          lockdown_level: ba.lockdown_level || '',
        });
      }

      // Populate fit profile
      if (data.fit_profile) {
        const fp = data.fit_profile;
        setFitProfile({
          size_runs: fp.size_runs || '',
          size_offset: fp.size_offset?.toString() || '',
          width_runs: fp.width_runs || '',
          toe_box_room: fp.toe_box_room || '',
          heel_fit: fp.heel_fit || '',
          midfoot_fit: fp.midfoot_fit || '',
          arch_support: fp.arch_support || '',
          break_in_period: fp.break_in_period || '',
          expected_miles_min: fp.expected_miles_min?.toString() || '',
          expected_miles_max: fp.expected_miles_max?.toString() || '',
          durability_rating: fp.durability_rating || '',
        });
      }
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to load shoe',
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      // Build update payload
      const updateData: Record<string, unknown> = {
        name: basicInfo.name || undefined,
        msrp_usd: basicInfo.msrp_usd ? parseFloat(basicInfo.msrp_usd) : undefined,
        is_active: basicInfo.is_active,
        is_discontinued: basicInfo.is_discontinued,
      };

      // Add category-specific attributes
      if (shoe?.category === 'running') {
        updateData.running_attributes = {
          weight_oz: runningAttrs.weight_oz ? parseFloat(runningAttrs.weight_oz) : null,
          drop_mm: runningAttrs.drop_mm ? parseFloat(runningAttrs.drop_mm) : null,
          stack_height_heel_mm: runningAttrs.stack_height_heel_mm ? parseFloat(runningAttrs.stack_height_heel_mm) : null,
          stack_height_forefoot_mm: runningAttrs.stack_height_forefoot_mm ? parseFloat(runningAttrs.stack_height_forefoot_mm) : null,
          terrain: runningAttrs.terrain || null,
          subcategory: runningAttrs.subcategory || null,
          cushion_type: runningAttrs.cushion_type || null,
          cushion_level: runningAttrs.cushion_level || null,
          has_carbon_plate: runningAttrs.has_carbon_plate,
          has_rocker: runningAttrs.has_rocker,
        };
      } else if (shoe?.category === 'basketball') {
        updateData.basketball_attributes = {
          weight_oz: basketballAttrs.weight_oz ? parseFloat(basketballAttrs.weight_oz) : null,
          cut: basketballAttrs.cut || null,
          court_type: basketballAttrs.court_type || null,
          cushion_type: basketballAttrs.cushion_type || null,
          cushion_level: basketballAttrs.cushion_level || null,
          traction_pattern: basketballAttrs.traction_pattern || null,
          ankle_support_level: basketballAttrs.ankle_support_level || null,
          lockdown_level: basketballAttrs.lockdown_level || null,
        };
      }

      await adminApi.updateShoe(shoeId, updateData);

      // Update fit profile separately
      await adminApi.updateFitProfile(shoeId, {
        size_runs: fitProfile.size_runs || undefined,
        size_offset: fitProfile.size_offset ? parseFloat(fitProfile.size_offset) : undefined,
        width_runs: fitProfile.width_runs || undefined,
        toe_box_room: fitProfile.toe_box_room || undefined,
        heel_fit: fitProfile.heel_fit || undefined,
        midfoot_fit: fitProfile.midfoot_fit || undefined,
        arch_support: fitProfile.arch_support || undefined,
        break_in_period: fitProfile.break_in_period || undefined,
        expected_miles_min: fitProfile.expected_miles_min ? parseInt(fitProfile.expected_miles_min) : undefined,
        expected_miles_max: fitProfile.expected_miles_max ? parseInt(fitProfile.expected_miles_max) : undefined,
        durability_rating: fitProfile.durability_rating || undefined,
      });

      toast({
        title: 'Saved',
        description: 'Shoe updated successfully',
      });

      // Reload to get fresh data
      loadShoe();
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to save changes',
        variant: 'destructive',
      });
    } finally {
      setSaving(false);
    }
  };

  // Calculate completeness
  const getMissingFields = () => {
    const missing: string[] = [];

    if (!basicInfo.msrp_usd) missing.push('MSRP');

    if (shoe?.category === 'running') {
      if (!runningAttrs.weight_oz) missing.push('Weight');
      if (!runningAttrs.drop_mm) missing.push('Drop');
      if (!runningAttrs.stack_height_heel_mm) missing.push('Heel Stack');
      if (!runningAttrs.stack_height_forefoot_mm) missing.push('Forefoot Stack');
      if (!runningAttrs.terrain) missing.push('Terrain');
      if (!runningAttrs.subcategory) missing.push('Category');
      if (!runningAttrs.cushion_type) missing.push('Cushion Type');
      if (!runningAttrs.cushion_level) missing.push('Cushion Level');
    }

    if (shoe?.category === 'basketball') {
      if (!basketballAttrs.weight_oz) missing.push('Weight');
      if (!basketballAttrs.cut) missing.push('Cut');
      if (!basketballAttrs.cushion_type) missing.push('Cushion Type');
    }

    return missing;
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-[400px] w-full" />
      </div>
    );
  }

  if (!shoe) {
    return <div>Shoe not found</div>;
  }

  const missingFields = getMissingFields();
  const isComplete = missingFields.length === 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link href="/admin/shoes">
            <Button variant="ghost" size="icon">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <div>
            <h1 className="text-2xl font-bold">{shoe.name}</h1>
            <p className="text-muted-foreground">{shoe.brand}</p>
          </div>
          <Badge variant="outline" className="capitalize">
            {shoe.category}
          </Badge>
        </div>
        <Button onClick={handleSave} disabled={saving}>
          <Save className="h-4 w-4 mr-2" />
          {saving ? 'Saving...' : 'Save Changes'}
        </Button>
      </div>

      {/* Completeness indicator */}
      <Card className={isComplete ? 'border-green-200 bg-green-50' : 'border-yellow-200 bg-yellow-50'}>
        <CardContent className="p-4">
          <div className="flex items-center gap-2">
            {isComplete ? (
              <>
                <CheckCircle2 className="h-5 w-5 text-green-600" />
                <span className="font-medium text-green-800">All required fields complete</span>
              </>
            ) : (
              <>
                <AlertTriangle className="h-5 w-5 text-yellow-600" />
                <span className="font-medium text-yellow-800">
                  Missing: {missingFields.join(', ')}
                </span>
              </>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Main content */}
      <Tabs defaultValue="specs">
        <TabsList>
          <TabsTrigger value="specs">Specs</TabsTrigger>
          <TabsTrigger value="fit">Fit Profile</TabsTrigger>
          <TabsTrigger value="basic">Basic Info</TabsTrigger>
        </TabsList>

        {/* Specs Tab */}
        <TabsContent value="specs" className="space-y-6">
          {shoe.category === 'running' && (
            <Card>
              <CardHeader>
                <CardTitle>Running Specs</CardTitle>
                <CardDescription>Technical specifications for this running shoe</CardDescription>
              </CardHeader>
              <CardContent className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="weight">Weight (oz)</Label>
                  <Input
                    id="weight"
                    type="number"
                    step="0.1"
                    placeholder="e.g. 9.5"
                    value={runningAttrs.weight_oz}
                    onChange={(e) => setRunningAttrs({ ...runningAttrs, weight_oz: e.target.value })}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="drop">Drop (mm)</Label>
                  <Input
                    id="drop"
                    type="number"
                    step="0.5"
                    placeholder="e.g. 8"
                    value={runningAttrs.drop_mm}
                    onChange={(e) => setRunningAttrs({ ...runningAttrs, drop_mm: e.target.value })}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="heel_stack">Heel Stack (mm)</Label>
                  <Input
                    id="heel_stack"
                    type="number"
                    step="0.5"
                    placeholder="e.g. 38"
                    value={runningAttrs.stack_height_heel_mm}
                    onChange={(e) => setRunningAttrs({ ...runningAttrs, stack_height_heel_mm: e.target.value })}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="forefoot_stack">Forefoot Stack (mm)</Label>
                  <Input
                    id="forefoot_stack"
                    type="number"
                    step="0.5"
                    placeholder="e.g. 30"
                    value={runningAttrs.stack_height_forefoot_mm}
                    onChange={(e) => setRunningAttrs({ ...runningAttrs, stack_height_forefoot_mm: e.target.value })}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="terrain">Terrain</Label>
                  <Select
                    value={runningAttrs.terrain}
                    onValueChange={(value) => setRunningAttrs({ ...runningAttrs, terrain: value })}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select terrain" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="road">Road</SelectItem>
                      <SelectItem value="trail">Trail</SelectItem>
                      <SelectItem value="track">Track</SelectItem>
                      <SelectItem value="hybrid">Hybrid</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="subcategory">Category</Label>
                  <Select
                    value={runningAttrs.subcategory}
                    onValueChange={(value) => setRunningAttrs({ ...runningAttrs, subcategory: value })}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select category" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="neutral">Neutral</SelectItem>
                      <SelectItem value="stability">Stability</SelectItem>
                      <SelectItem value="motion_control">Motion Control</SelectItem>
                      <SelectItem value="racing">Racing</SelectItem>
                      <SelectItem value="daily_trainer">Daily Trainer</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="cushion_type">Cushion Type</Label>
                  <Input
                    id="cushion_type"
                    placeholder="e.g. ZoomX, Fresh Foam"
                    value={runningAttrs.cushion_type}
                    onChange={(e) => setRunningAttrs({ ...runningAttrs, cushion_type: e.target.value })}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="cushion_level">Cushion Level</Label>
                  <Select
                    value={runningAttrs.cushion_level}
                    onValueChange={(value) => setRunningAttrs({ ...runningAttrs, cushion_level: value })}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select level" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="minimal">Minimal</SelectItem>
                      <SelectItem value="moderate">Moderate</SelectItem>
                      <SelectItem value="max">Max</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="flex items-center space-x-2 col-span-2">
                  <Switch
                    id="carbon_plate"
                    checked={runningAttrs.has_carbon_plate}
                    onCheckedChange={(checked) => setRunningAttrs({ ...runningAttrs, has_carbon_plate: checked })}
                  />
                  <Label htmlFor="carbon_plate">Has Carbon Plate</Label>
                </div>

                <div className="flex items-center space-x-2 col-span-2">
                  <Switch
                    id="rocker"
                    checked={runningAttrs.has_rocker}
                    onCheckedChange={(checked) => setRunningAttrs({ ...runningAttrs, has_rocker: checked })}
                  />
                  <Label htmlFor="rocker">Has Rocker Geometry</Label>
                </div>
              </CardContent>
            </Card>
          )}

          {shoe.category === 'basketball' && (
            <Card>
              <CardHeader>
                <CardTitle>Basketball Specs</CardTitle>
                <CardDescription>Technical specifications for this basketball shoe</CardDescription>
              </CardHeader>
              <CardContent className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="bb_weight">Weight (oz)</Label>
                  <Input
                    id="bb_weight"
                    type="number"
                    step="0.1"
                    placeholder="e.g. 14.5"
                    value={basketballAttrs.weight_oz}
                    onChange={(e) => setBasketballAttrs({ ...basketballAttrs, weight_oz: e.target.value })}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="cut">Cut</Label>
                  <Select
                    value={basketballAttrs.cut}
                    onValueChange={(value) => setBasketballAttrs({ ...basketballAttrs, cut: value })}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select cut" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="low">Low</SelectItem>
                      <SelectItem value="mid">Mid</SelectItem>
                      <SelectItem value="high">High</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="court_type">Court Type</Label>
                  <Select
                    value={basketballAttrs.court_type}
                    onValueChange={(value) => setBasketballAttrs({ ...basketballAttrs, court_type: value })}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select court" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="indoor">Indoor</SelectItem>
                      <SelectItem value="outdoor">Outdoor</SelectItem>
                      <SelectItem value="both">Both</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="bb_cushion_type">Cushion Type</Label>
                  <Input
                    id="bb_cushion_type"
                    placeholder="e.g. Zoom Air, React"
                    value={basketballAttrs.cushion_type}
                    onChange={(e) => setBasketballAttrs({ ...basketballAttrs, cushion_type: e.target.value })}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="bb_cushion_level">Cushion Level</Label>
                  <Select
                    value={basketballAttrs.cushion_level}
                    onValueChange={(value) => setBasketballAttrs({ ...basketballAttrs, cushion_level: value })}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select level" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="minimal">Minimal</SelectItem>
                      <SelectItem value="moderate">Moderate</SelectItem>
                      <SelectItem value="max">Max</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="traction">Traction Pattern</Label>
                  <Input
                    id="traction"
                    placeholder="e.g. herringbone, multi-directional"
                    value={basketballAttrs.traction_pattern}
                    onChange={(e) => setBasketballAttrs({ ...basketballAttrs, traction_pattern: e.target.value })}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="ankle_support">Ankle Support</Label>
                  <Select
                    value={basketballAttrs.ankle_support_level}
                    onValueChange={(value) => setBasketballAttrs({ ...basketballAttrs, ankle_support_level: value })}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select level" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="low">Low</SelectItem>
                      <SelectItem value="medium">Medium</SelectItem>
                      <SelectItem value="high">High</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="lockdown">Lockdown</Label>
                  <Select
                    value={basketballAttrs.lockdown_level}
                    onValueChange={(value) => setBasketballAttrs({ ...basketballAttrs, lockdown_level: value })}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select level" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="low">Low</SelectItem>
                      <SelectItem value="medium">Medium</SelectItem>
                      <SelectItem value="high">High</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Fit Profile Tab */}
        <TabsContent value="fit" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Fit Profile</CardTitle>
              <CardDescription>How this shoe fits different foot types</CardDescription>
            </CardHeader>
            <CardContent className="grid grid-cols-2 md:grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label htmlFor="size_runs">Size Runs</Label>
                <Select
                  value={fitProfile.size_runs}
                  onValueChange={(value) => setFitProfile({ ...fitProfile, size_runs: value })}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="small">Runs Small</SelectItem>
                    <SelectItem value="true_to_size">True to Size</SelectItem>
                    <SelectItem value="large">Runs Large</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="size_offset">Size Offset</Label>
                <Input
                  id="size_offset"
                  type="number"
                  step="0.5"
                  placeholder="e.g. -0.5, 0, +0.5"
                  value={fitProfile.size_offset}
                  onChange={(e) => setFitProfile({ ...fitProfile, size_offset: e.target.value })}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="width_runs">Width Runs</Label>
                <Select
                  value={fitProfile.width_runs}
                  onValueChange={(value) => setFitProfile({ ...fitProfile, width_runs: value })}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="narrow">Runs Narrow</SelectItem>
                    <SelectItem value="standard">Standard</SelectItem>
                    <SelectItem value="wide">Runs Wide</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="toe_box">Toe Box</Label>
                <Select
                  value={fitProfile.toe_box_room}
                  onValueChange={(value) => setFitProfile({ ...fitProfile, toe_box_room: value })}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="cramped">Cramped</SelectItem>
                    <SelectItem value="snug">Snug</SelectItem>
                    <SelectItem value="standard">Standard</SelectItem>
                    <SelectItem value="roomy">Roomy</SelectItem>
                    <SelectItem value="spacious">Spacious</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="heel_fit">Heel Fit</Label>
                <Select
                  value={fitProfile.heel_fit}
                  onValueChange={(value) => setFitProfile({ ...fitProfile, heel_fit: value })}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="loose">Loose</SelectItem>
                    <SelectItem value="standard">Standard</SelectItem>
                    <SelectItem value="secure">Secure</SelectItem>
                    <SelectItem value="tight">Tight</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="midfoot_fit">Midfoot Fit</Label>
                <Select
                  value={fitProfile.midfoot_fit}
                  onValueChange={(value) => setFitProfile({ ...fitProfile, midfoot_fit: value })}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="loose">Loose</SelectItem>
                    <SelectItem value="standard">Standard</SelectItem>
                    <SelectItem value="secure">Secure</SelectItem>
                    <SelectItem value="tight">Tight</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="arch_support">Arch Support</Label>
                <Select
                  value={fitProfile.arch_support}
                  onValueChange={(value) => setFitProfile({ ...fitProfile, arch_support: value })}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="minimal">Minimal</SelectItem>
                    <SelectItem value="moderate">Moderate</SelectItem>
                    <SelectItem value="substantial">Substantial</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="break_in">Break-in Period</Label>
                <Select
                  value={fitProfile.break_in_period}
                  onValueChange={(value) => setFitProfile({ ...fitProfile, break_in_period: value })}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">None</SelectItem>
                    <SelectItem value="minimal">Minimal (1-2 runs)</SelectItem>
                    <SelectItem value="moderate">Moderate (3-5 runs)</SelectItem>
                    <SelectItem value="extended">Extended (5+ runs)</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="durability">Durability Rating</Label>
                <Select
                  value={fitProfile.durability_rating}
                  onValueChange={(value) => setFitProfile({ ...fitProfile, durability_rating: value })}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="low">Low (under 300 mi)</SelectItem>
                    <SelectItem value="average">Average (300-500 mi)</SelectItem>
                    <SelectItem value="high">High (500+ mi)</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="miles_min">Expected Miles Min</Label>
                <Input
                  id="miles_min"
                  type="number"
                  placeholder="e.g. 300"
                  value={fitProfile.expected_miles_min}
                  onChange={(e) => setFitProfile({ ...fitProfile, expected_miles_min: e.target.value })}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="miles_max">Expected Miles Max</Label>
                <Input
                  id="miles_max"
                  type="number"
                  placeholder="e.g. 500"
                  value={fitProfile.expected_miles_max}
                  onChange={(e) => setFitProfile({ ...fitProfile, expected_miles_max: e.target.value })}
                />
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Basic Info Tab */}
        <TabsContent value="basic" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Basic Information</CardTitle>
              <CardDescription>General shoe information</CardDescription>
            </CardHeader>
            <CardContent className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="name">Name</Label>
                <Input
                  id="name"
                  value={basicInfo.name}
                  onChange={(e) => setBasicInfo({ ...basicInfo, name: e.target.value })}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="msrp">MSRP (USD)</Label>
                <Input
                  id="msrp"
                  type="number"
                  step="1"
                  placeholder="e.g. 160"
                  value={basicInfo.msrp_usd}
                  onChange={(e) => setBasicInfo({ ...basicInfo, msrp_usd: e.target.value })}
                />
              </div>

              <div className="flex items-center space-x-2">
                <Switch
                  id="active"
                  checked={basicInfo.is_active}
                  onCheckedChange={(checked) => setBasicInfo({ ...basicInfo, is_active: checked })}
                />
                <Label htmlFor="active">Active</Label>
              </div>

              <div className="flex items-center space-x-2">
                <Switch
                  id="discontinued"
                  checked={basicInfo.is_discontinued}
                  onCheckedChange={(checked) => setBasicInfo({ ...basicInfo, is_discontinued: checked })}
                />
                <Label htmlFor="discontinued">Discontinued</Label>
              </div>
            </CardContent>
          </Card>

          {/* Meta info */}
          <Card>
            <CardHeader>
              <CardTitle>Metadata</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm text-muted-foreground">
              <p><strong>ID:</strong> {shoe.id}</p>
              <p><strong>Slug:</strong> {shoe.slug}</p>
              <p><strong>Brand ID:</strong> {shoe.brand_id}</p>
              <p><strong>Category ID:</strong> {shoe.category_id}</p>
              <p><strong>Last Scraped:</strong> {shoe.last_scraped_at ? new Date(shoe.last_scraped_at).toLocaleString() : 'Never'}</p>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
