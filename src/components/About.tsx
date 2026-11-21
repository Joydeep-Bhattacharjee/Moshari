import {
  CloudRain,
  MapPin,
  CalendarDays,
  Layers3,
  ShieldCheck,
  Check,
  Radar,
  FlaskConical,
  Database,
} from "lucide-react";
import { CardHeader } from "./DashboardUI";
import type { TEXTS } from "../data";

type TextKey = keyof typeof TEXTS.en;

export default function About({
  l,
  t,
}: {
  l: (a: string, b: string) => string;
  t: (k: TextKey) => string;
}) {
  const bullets = [
    [
      CloudRain,
      l("Read the weather. See what’s coming.", "আবহাওয়া বুঝুন। আগাম জানুন।"),
      l(
        "Multi-week rainfall, temperature, and humidity lags reveal the conditions that precede dengue outbreaks.",
        "কয়েক সপ্তাহের বৃষ্টিপাত, তাপমাত্রা ও আর্দ্রতার তথ্য ডেঙ্গুর অনুকূল পরিবেশ চিহ্নিত করে।",
      ),
    ],
    [
      MapPin,
      l("Every ward has its own story.", "প্রতিটি ওয়ার্ডের গল্প আলাদা।"),
      l(
        "Waterlogging, population density, and sanitation make the forecast sensitive to local vulnerability.",
        "জলাবদ্ধতা, জনঘনত্ব ও স্যানিটেশন স্থানীয় ঝুঁকি বুঝতে সাহায্য করে।",
      ),
    ],
    [
      CalendarDays,
      l("Two, three, or four weeks to prepare.", "প্রস্তুতির জন্য দুই, তিন বা চার সপ্তাহ।"),
      l(
        "Choose a forecast horizon and see risk tiers, case estimates, and an honest 80% uncertainty interval.",
        "পূর্বাভাসের সময়সীমা বেছে ঝুঁকি, সম্ভাব্য কেস ও ৮০% অনিশ্চয়তা সীমা দেখুন।",
      ),
    ],
    [
      Layers3,
      l("Turn predictions into priorities.", "পূর্বাভাস থেকে অগ্রাধিকার।"),
      l(
        "Rank every ward, explore rainfall scenarios, and download a ready-to-use spray-team priority list.",
        "ওয়ার্ডের অগ্রাধিকার সাজান, বৃষ্টিপাতের সম্ভাবনা দেখুন এবং স্প্রে দলের তালিকা নামান।",
      ),
    ],
    [
      ShieldCheck,
      l("Evidence first. Always.", "সবার আগে প্রমাণ।"),
      l(
        "Chronological backtesting, a four-week purge gap, and alert metrics keep performance transparent.",
        "সময়ানুক্রমিক যাচাই, চার সপ্তাহের বিরতি ও সতর্কতা পরিমাপ কার্যকারিতা স্বচ্ছ রাখে।",
      ),
    ],
  ] as const;

  return (
    <div className="about-page">
      <section className="about-hero card">
        <span className="about-radar">
          <Radar size={42} strokeWidth={1.25} />
        </span>
        <div className="eyebrow">MOSHARI · PRD v2</div>
        <h2>{l("A head start against dengue.", "ডেঙ্গুর বিরুদ্ধে আগাম প্রস্তুতি।")}</h2>
        <p>
          {l(
            "Local signals, thoughtfully connected — so public health teams can act sooner, where it matters most.",
            "স্থানীয় তথ্যের সমন্বয়ে জনস্বাস্থ্য দল সঠিক জায়গায় আগেই পদক্ষেপ নিতে পারে।",
          )}
        </p>
        <div className="about-tags">
          <span>
            <Check size={13} />
            {l("Ward-level", "ওয়ার্ডভিত্তিক")}
          </span>
          <span>
            <Check size={13} />
            {l("Bilingual", "দ্বিভাষিক")}
          </span>
          <span>
            <Check size={13} />
            {l("No external APIs", "বাহ্যিক API নেই")}
          </span>
        </div>
      </section>

      <section className="card about-bullets">
        {bullets.map(([Icon, title, text], i) => (
          <div className="about-bullet" key={title}>
            <span className="about-step">
              <Icon size={20} />
            </span>
            <div>
              <span className="step-number">0{i + 1}</span>
              <h3>{title}</h3>
              <p>{text}</p>
            </div>
          </div>
        ))}
      </section>

      <div className="about-bottom">
        <section className="card">
          <FlaskConical size={22} />
          <h3>{t("mock")}</h3>
          <p>
            {l(
              "This frontend uses deterministic, realistic sample data while the backend, feature pipeline, and models are in development. Demo outputs are not clinical guidance.",
              "ব্যাকএন্ড, ফিচার পাইপলাইন ও মডেল তৈরির সময় এই ফ্রন্টএন্ডে বাস্তবসম্মত নমুনা তথ্য ব্যবহার করা হচ্ছে। এটি চিকিৎসা নির্দেশনা নয়।",
            )}
          </p>
        </section>

        <section className="card">
          <Database size={22} />
          <h3>{l("Local by design", "স্থানীয় ব্যবহারের জন্য")}</h3>
          <p className="cost-line">0 API calls, 0 LLM tokens</p>
          <p>
            {l(
              "0 API calls, 0 LLM tokens, model trained on Jan 2023 – Dec 2024 (illustrative mock dates).",
              "0 API calls, 0 LLM tokens, মডেলের প্রশিক্ষণকাল জানুয়ারি ২০২৩ – ডিসেম্বর ২০২৪ (নমুনা তারিখ)।",
            )}
          </p>
          <span className="subtle-pill">
            {l("Mock adapter: src/data.ts", "নমুনা অ্যাডাপ্টার: src/data.ts")}
          </span>
        </section>
      </div>
    </div>
  );
}