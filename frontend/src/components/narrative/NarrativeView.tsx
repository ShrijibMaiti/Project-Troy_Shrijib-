import CitationChip from '@/components/evidence/CitationChip';
import ConfidenceBadge from '@/components/evidence/ConfidenceBadge';
import ArtifactMeta from '@/components/narrative/ArtifactMeta';
import type { ArtifactMeta as ArtifactMetaType, NarrativeSentence, Signal } from '@/types/api';

interface Props {
  narrative: NarrativeSentence[];
  signals: Signal[];
  activeSignal: number;
  artifactMeta: ArtifactMetaType;
  onLocate: (n: number) => void;
  onDispute: (n: number) => void;
}

/** The generated, cited, pinned narrative: every sentence carries its citation chip and confidence tier. */
export default function NarrativeView({ narrative, signals, activeSignal, artifactMeta, onLocate, onDispute }: Props) {
  return (
    <div className="border border-line bg-panel">
      <div className="flex items-center justify-between border-b border-line px-[22px] py-4">
        <span className="font-mono text-[10px] tracking-[.16em] text-mute">
          ANALYST NARRATIVE — GENERATED, CITED, PINNED
        </span>
        <span className="font-mono text-[9.5px] text-faint">HOVER A CHIP TO PREVIEW · CLICK TO LOCATE</span>
      </div>
      <div className="px-[26px] py-6 text-[15px] leading-[2.05] text-fg-body">
        {narrative.map((sn, i) => {
          const sig = signals[sn.n - 1];
          return (
            <span key={i}>
              <span>{sn.text}</span>
              <CitationChip
                n={sn.n}
                active={activeSignal === sn.n}
                date={sig.date}
                source={sig.src}
                excerpt={sig.excerpt}
                onLocate={onLocate}
              />{' '}
              <ConfidenceBadge conf={sn.conf} small />
              {sn.disputable && (
                <button
                  onClick={() => onDispute(sn.n)}
                  className="ml-0.5 cursor-pointer rounded-sm border border-line-2 bg-transparent px-[7px] py-0.5 align-[2px] font-mono text-[9px] tracking-[.08em] text-mute hover:border-tint-amber-border hover:text-risk-amber"
                >
                  DISPUTE
                </button>
              )}{' '}
            </span>
          );
        })}
      </div>
      <ArtifactMeta meta={artifactMeta} />
    </div>
  );
}
