import { useState } from 'react';
import { extractContract, saveContract, type ContractDraftOut } from '@/lib/api';

interface Props {
  vendorId: string;
  vendorName: string;
  open: boolean;
  onClose: () => void;
  onSaved: () => void;
}

/** Fields shown for review, in register order. */
const FIELDS: { key: string; label: string; required?: boolean }[] = [
  { key: 'contractual_arrangement_ref', label: 'Arrangement reference', required: true },
  { key: 'provider_legal_name', label: 'Provider legal name', required: true },
  { key: 'provider_lei', label: 'Provider LEI' },
  { key: 'provider_country', label: 'Provider country' },
  { key: 'function_identifier', label: 'Function identifier' },
  { key: 'function_name', label: 'Function name' },
  { key: 'ict_service_type', label: 'ICT service type' },
  { key: 'supports_critical_function', label: 'Supports critical function' },
  { key: 'start_date', label: 'Start date' },
  { key: 'end_date', label: 'End date' },
  { key: 'notice_period_days', label: 'Notice period (days)' },
  { key: 'governing_law_country', label: 'Governing law' },
  { key: 'annual_cost_eur', label: 'Annual cost (EUR)' },
  { key: 'data_location_countries', label: 'Data locations' },
  { key: 'processing_location_countries', label: 'Processing locations' },
  { key: 'sensitive_data_involved', label: 'Sensitive data' },
  { key: 'substitutability', label: 'Substitutability' },
  { key: 'exit_plan_exists', label: 'Exit plan exists' },
  { key: 'exit_plan_last_tested', label: 'Exit plan last tested' },
  { key: 'reintegration_possible', label: 'Reintegration possible' },
];

function toInput(v: any): string {
  if (v === null || v === undefined) return '';
  if (Array.isArray(v)) return v.join(', ');
  if (typeof v === 'boolean') return v ? 'true' : 'false';
  return String(v);
}

function fromInput(key: string, s: string): any {
  const t = s.trim();
  if (t === '') return null;
  if (key.endsWith('_countries')) return t.split(',').map((x) => x.trim().toUpperCase()).filter(Boolean);
  if (['supports_critical_function', 'sensitive_data_involved', 'exit_plan_exists', 'reintegration_possible'].includes(key))
    return t.toLowerCase() === 'true';
  if (['notice_period_days', 'annual_cost_eur'].includes(key)) {
    const n = parseInt(t.replace(/[^\d]/g, ''), 10);
    return Number.isNaN(n) ? null : n;
  }
  return t;
}

export default function ContractExtractDialog({ vendorId, vendorName, open, onClose, onSaved }: Props) {
  const [phase, setPhase] = useState<'pick' | 'reading' | 'review' | 'saving'>('pick');
  const [result, setResult] = useState<ContractDraftOut | null>(null);
  const [values, setValues] = useState<Record<string, string>>({});
  const [error, setError] = useState('');

  if (!open) return null;

  const reset = () => { setPhase('pick'); setResult(null); setValues({}); setError(''); };
  const close = () => { reset(); onClose(); };

  const onFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f) return;
    setPhase('reading'); setError('');
    try {
      const r = await extractContract(vendorId, f);
      setResult(r);
      const v: Record<string, string> = {};
      for (const fld of FIELDS) v[fld.key] = toInput(r.draft[fld.key]);
      setValues(v);
      setPhase('review');
    } catch (err: any) {
      setError(String(err?.message ?? err));
      setPhase('pick');
    }
  };

  const missingRequired = FIELDS.filter((f) => f.required && !values[f.key]?.trim()).map((f) => f.label);

  const confirm = async () => {
    if (missingRequired.length) return;
    setPhase('saving'); setError('');
    try {
      const payload: Record<string, any> = {};
      for (const f of FIELDS) payload[f.key] = fromInput(f.key, values[f.key] ?? '');
      payload.subcontractors = result?.draft.subcontractors ?? [];
      await saveContract(vendorId, payload);
      onSaved();
      close();
    } catch (err: any) {
      setError(String(err?.message ?? err));
      setPhase('review');
    }
  };

  const confColor = (c: number | undefined) =>
    c === undefined ? 'text-faint' : c >= 0.8 ? 'text-risk-green' : c >= 0.6 ? 'text-risk-amber' : 'text-risk-red';

  return (
    <div className="fixed inset-0 z-[200] flex items-start justify-center overflow-y-auto bg-black/70 p-8">
      <div className="w-full max-w-[900px] border border-line bg-panel">
        <div className="flex items-center justify-between border-b border-line px-6 py-4">
          <div>
            <div className="font-mono text-[10px] tracking-[.16em] text-mute">EXTRACT CONTRACT FIELDS</div>
            <div className="mt-1 text-[15px] font-semibold">{vendorName}</div>
          </div>
          <button onClick={close} className="cursor-pointer border-none bg-transparent font-mono text-lg text-mute hover:text-fg">
            ✕
          </button>
        </div>

        {error && (
          <div className="border-b border-tint-red-line bg-tint-red-bg2 px-6 py-3 font-mono text-[11px] text-risk-red">
            {error}
          </div>
        )}

        {phase === 'pick' && (
          <div className="px-6 py-8">
            <p className="mb-5 mt-0 text-[13.5px] leading-relaxed text-dim">
              Upload the ICT services agreement. Gemma 4 reads it and drafts the register fields — every
              extracted value carries the verbatim clause it came from. <b>Nothing is saved</b> until you
              review and confirm. The document is discarded after extraction; Troy does not store contracts.
            </p>
            <label className="inline-block cursor-pointer rounded-sm border border-line-3 px-5 py-3 font-mono text-[11px] tracking-[.1em] text-fg hover:border-mute">
              CHOOSE PDF
              <input type="file" accept="application/pdf" className="hidden" onChange={onFile} />
            </label>
          </div>
        )}

        {phase === 'reading' && (
          <div className="px-6 py-12 text-center">
            <div className="animate-pulse2 font-mono text-[11px] tracking-[.14em] text-risk-blue">
              READING DOCUMENT — GEMMA 4 VISION
            </div>
            <div className="mt-3 font-mono text-[10px] text-faint">extraction only · nothing is written</div>
          </div>
        )}

        {(phase === 'review' || phase === 'saving') && result && (
          <>
            <div className="flex items-center justify-between border-b border-line px-6 py-3 font-mono text-[10px] tracking-[.1em] text-dim">
              <span>MODEL {result.modelId}</span>
              <span>{result.unfound.length} FIELD(S) NOT FOUND IN DOCUMENT</span>
            </div>

            <div className="max-h-[52vh] overflow-y-auto">
              {FIELDS.map((f) => {
                const conf = result.confidence[f.key];
                const ev = result.evidence[f.key];
                return (
                  <div key={f.key} className="border-b border-line-row px-6 py-3">
                    <div className="flex items-center gap-4">
                      <span className="w-[190px] flex-none font-mono text-[10px] tracking-[.06em] text-mute">
                        {f.label}
                        {f.required && <span className="text-risk-red"> *</span>}
                      </span>
                      <input
                        value={values[f.key] ?? ''}
                        onChange={(e) => setValues({ ...values, [f.key]: e.target.value })}
                        className="flex-1 rounded-sm border border-line-3 bg-field px-3 py-2 font-mono text-[11.5px] text-fg outline-none focus:border-mute"
                      />
                      <span className={`w-[40px] text-right font-mono text-[10px] ${confColor(conf)}`}>
                        {conf === undefined ? '—' : conf.toFixed(2)}
                      </span>
                    </div>
                    {ev && (
                      <div className="ml-[206px] mt-1.5 border-l border-line-2 pl-3 font-mono text-[9.5px] leading-relaxed text-faint">
                        “{ev}”
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            <div className="flex items-center justify-between border-t border-line px-6 py-4">
              <span className="font-mono text-[9.5px] leading-relaxed text-faint">
                {missingRequired.length
                  ? `REQUIRED: ${missingRequired.join(', ')}`
                  : 'Confirmed values are written to the register and versioned. The draft itself is never saved.'}
              </span>
              <div className="flex gap-2.5">
                <button
                  onClick={close}
                  className="cursor-pointer rounded-sm border border-line-3 bg-transparent px-4 py-2.5 font-mono text-[10px] tracking-[.1em] text-dim hover:border-mute"
                >
                  CANCEL
                </button>
                <button
                  onClick={confirm}
                  disabled={phase === 'saving' || missingRequired.length > 0}
                  className="cursor-pointer rounded-sm border-none bg-fg px-4 py-2.5 font-mono text-[10px] tracking-[.1em] text-ink hover:bg-white disabled:cursor-not-allowed disabled:opacity-40"
                >
                  {phase === 'saving' ? 'SAVING…' : 'CONFIRM & SAVE →'}
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}