interface Props {
  score: number;
  color?: string;
}

export default function ScoreDial({ score, color = '#E5484D' }: Props) {
  const dash = `${((score / 100) * 314).toFixed(0)} 314`;
  return (
    <svg viewBox="0 0 120 120" className="h-[110px] w-[110px]">
      <circle cx="60" cy="60" r="50" fill="none" stroke="#1C1C20" strokeWidth="6" />
      <circle
        cx="60"
        cy="60"
        r="50"
        fill="none"
        stroke={color}
        strokeWidth="6"
        strokeLinecap="butt"
        strokeDasharray={dash}
        transform="rotate(-90 60 60)"
      />
      <text x="60" y="64" textAnchor="middle" fill="#E6E4DF" fontFamily="Sometype Mono" fontSize="30" fontWeight="600">
        {score}
      </text>
      <text x="60" y="82" textAnchor="middle" fill="#55555C" fontFamily="Sometype Mono" fontSize="8" letterSpacing="2">
        RISK / 100
      </text>
    </svg>
  );
}
