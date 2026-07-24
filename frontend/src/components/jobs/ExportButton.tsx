interface Props {
  label: string;
  variant: 'primary' | 'outline';
  onClick: () => void;
}

/** Export trigger — starts a server-side job (see JobProgress); the click never blocks on the artifact. */
export default function ExportButton({ label, variant, onClick }: Props) {
  return (
    <button
      onClick={onClick}
      className={
        variant === 'primary'
          ? 'cursor-pointer rounded-sm border-none bg-fg px-[18px] py-[11px] font-mono text-[10px] tracking-[.1em] text-ink hover:bg-white'
          : 'cursor-pointer rounded-sm border border-line-3 bg-transparent px-[18px] py-[11px] font-mono text-[10px] tracking-[.1em] text-fg hover:border-mute'
      }
    >
      {label}
    </button>
  );
}
