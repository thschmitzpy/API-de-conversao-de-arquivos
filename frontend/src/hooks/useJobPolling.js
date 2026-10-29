import { useEffect, useState } from 'react';
import { consultarJob, mensagemDeErro } from '../services/api';

// 1,5 s fica em 40 req/min, abaixo do limite de 60/min do GET /jobs/{id}.
const INTERVALO_MS = 1500;
const ESPERA_APOS_429_MS = 10000;
const MAX_FALHAS_SEGUIDAS = 5;
const STATUS_FINAIS = ['DONE', 'FAILED'];

export default function useJobPolling(jobId) {
  const [job, setJob] = useState(null);
  const [erro, setErro] = useState(null);

  useEffect(() => {
    if (!jobId) {
      return undefined;
    }

    const controle = new AbortController();
    let timer = null;
    let falhas = 0;

    async function consultar() {
      try {
        const atual = await consultarJob(jobId, controle.signal);
        falhas = 0;
        setJob(atual);
        if (!STATUS_FINAIS.includes(atual.status)) {
          timer = setTimeout(consultar, INTERVALO_MS);
        }
      } catch (e) {
        if (controle.signal.aborted) {
          return;
        }
        const status = e.response?.status;
        const transitorio = !status || status === 429 || status >= 500;
        falhas += 1;
        if (!transitorio || falhas >= MAX_FALHAS_SEGUIDAS) {
          setErro(mensagemDeErro(e));
          return;
        }
        timer = setTimeout(consultar, status === 429 ? ESPERA_APOS_429_MS : INTERVALO_MS * falhas);
      }
    }

    consultar();

    return () => {
      controle.abort();
      clearTimeout(timer);
    };
  }, [jobId]);

  return { job, erro };
}
