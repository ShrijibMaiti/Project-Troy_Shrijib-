import type { ArtifactMeta as ArtifactMetaType } from '@/types/api';

interface Props {
  meta: ArtifactMetaType;
}

/** The frozen-artifact footer: model_id · prompt_hash · generated_at. Retrieval, never re-inference. */
export default function ArtifactMeta({ meta }: Props) {
  return (
    <div className="flex flex-wrap gap-[22px] border-t border-line px-[22px] py-3.5">
      <span className="font-mono text-[9.5px] tracking-[.06em] text-mute">
        MODEL {meta.model} · PROMPT {meta.prompt} · GENERATED {meta.generatedAt}
      </span>
      <span className="font-mono text-[9.5px] tracking-[.06em] text-faint">
        FROZEN ARTIFACT — REPRODUCING THE MARCH REPORT IS A LOOKUP, NOT A RE-RUN
      </span>
    </div>
  );
}
