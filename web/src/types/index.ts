export type Speaker = "我" | "对方" | "未确认";

export type Platform = "微信" | "QQ" | "ChatLab" | "CSV" | "SQLite";

export interface MessageItem {
  id: string | number;
  speaker: Speaker;
  text: string;
  timestamp: string;
  senderName?: string;
  confidence?: number;
  done?: boolean;
  messageId?: string;
  // Analysis metadata
  rating?: {
    speaker: Speaker;
    score?: number | null; // 我方评级 0-100 (SSS-D)
    affinityDelta?: number | null; // 对方好感变化 -2 to +2
    confidence: number;
    boundary: number; // 0 to 1
    reason: string;
    source?: string;
    grade?: string;
  };
  issue?: {
    kind: string;
    reason: string;
  };
  explanation?: {
    text: string;
    source: string;
    createdAt: string;
  };
  emotion?: { label: string; probability: number }[];
  intent?: { label: string; probability: number }[];
}

export interface DimensionMetric {
  name: string;
  key: string;
  weight: number;
  score: number | null; // 0 - 100
  confidence: number; // 0 - 1
  evidence: string;
  description: string;
}

export interface ReplySuggestion {
  style: string;
  text: string;
  reason: string;
  tag?: string;
}

export interface AnalysisSummary {
  summary: string;
  selfLogic: string;
  otherLogic: string;
  overallScore: number | null;
  boundaryAlert: boolean;
  boundaryProbability: number;
  shouldWait: boolean;
  cautions: string[];
  replies: ReplySuggestion[];
  dimensions: DimensionMetric[];
  evaluatedAt: string;
  model: string;
}

export interface AffinityState {
  perspective: 'other' | 'self';
  score: number; initial: number; processed: number; pending: number; availableBatches: number;
  batches: { id: string; before: number; delta: number; after: number; confidence: number;
    summary: string; uncertainties: string[]; createdAt: string; model: string;
    personality?: { text: string; evidenceIds: number[] }[];
    pursuitAdvice?: { text: string; evidenceIds: number[] }[];
    evidence: { entryId: number; quote: string; signal: string; speaker: string }[] }[];
}

export interface ContactProfile {
  id: string;
  name: string;
  platform: Platform;
  avatarText: string;
  avatarBg: string;
  conversationKey: string;
  selfIdentity: string;
  messageCount: number;
  lastActive: string;
  healthSignal: number | null; // unknown evidence is not an estimated score
  signalLabel: string;
  unreadCount?: number;
  notes?: string;
}

export interface SettingsConfig {
  mode: "DeepSeek" | "TypeSafe Jev" | "Jev + DeepSeek";
  chatUrl: string;
  chatModel: string;
  chatKey: string;
  jevUrl: string;
  jevModel: string;
  jevKey: string;
  rememberKeys: boolean;
  useDpapi: boolean;
  autoAnalyze: boolean;
  interval: number;
  cooldown: number;
  fontSize: "dense" | "default" | "relaxed";
  theme: "dark" | "light" | "system";
  reducedMotion: boolean;
  hapticSound: boolean;
  hasChatKey?: boolean;
  hasJevKey?: boolean;
  fontFamily?: string;
  chatFontSize?: number;
  accent?: string;
  surface?: string;
  goal?: string;
  style?: string;
  selfOnRight?: boolean;
  guideDone?: boolean;
}
