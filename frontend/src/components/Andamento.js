import { useEffect, useState } from 'react';
import useJobPolling from '../hooks/useJobPolling';
import { formatarDuracao, formatarExpiracao } from '../formatar';
import { urlDownload } from '../services/api';

const ETAPAS = ['Envio', 'Na fila', 'Processando', 'Pronto'];

const MAX_TIMEOUT_MS = 2 ** 31 - 1;

function etapaAtual(jobId, job) {
  if (!jobId) {
    return 0;
  }
  if (!job || job.status === 'PENDING') {
    return 1;
  }
  if (job.status === 'DONE') {
    return 3;
  }
  return 2;
}

function classeEtapa(indice, atual, falhou, concluido) {
  if (concluido || indice < atual) {
    return 'etapa etapa--feita';
  }
  if (indice === atual) {
    return falhou ? 'etapa etapa--falha' : 'etapa etapa--atual';
  }
  return 'etapa';
}

export default function Andamento({
  nomeArquivo,
  titulo,
  progresso,
  jobId,
  erroEnvio,
  onVoltarAoArquivo,
  onRecomecar,
}) {
  const { job, erro: erroConsulta, consultarDeNovo } = useJobPolling(jobId);

  const erroJob = job?.status === 'FAILED' ? job.error_message || 'O processamento falhou.' : null;
  const falha = erroEnvio || erroConsulta || erroJob;
  const concluido = job?.status === 'DONE';
  const emAndamento = !falha && !concluido;
  const etapa = etapaAtual(jobId, job);
  const duracao = concluido ? formatarDuracao(job.created_at, job.finished_at) : null;
  const expiraEm = concluido ? job.expires_at : null;
  const [prazoVencido, setPrazoVencido] = useState(false);

  useEffect(() => {
    setPrazoVencido(false);
    if (!expiraEm) {
      return undefined;
    }
    const prazo = new Date(expiraEm).getTime();
    if (Number.isNaN(prazo)) {
      return undefined;
    }

    let timer = null;

    function conferir() {
      const restante = prazo - Date.now();
      if (restante <= 0) {
        setPrazoVencido(true);
        return;
      }
      timer = setTimeout(conferir, Math.min(restante, MAX_TIMEOUT_MS));
    }

    conferir();
    return () => clearTimeout(timer);
  }, [expiraEm]);

  const expirou = prazoVencido || Boolean(job?.files_purged_at);
  const validade = formatarExpiracao(expiraEm);

  return (
    <section className="painel andamento" aria-live="polite">
      <header className="andamento__cabecalho">
        <strong title={nomeArquivo}>{nomeArquivo}</strong>
        <span>{titulo}</span>
      </header>

      <ol className="etapas">
        {ETAPAS.map((nome, indice) => (
          <li key={nome} className={classeEtapa(indice, etapa, Boolean(falha), concluido)}>
            {nome}
          </li>
        ))}
      </ol>

      {emAndamento && etapa === 0 && (
        <>
          <div
            className="progresso"
            role="progressbar"
            aria-label="Envio do arquivo"
            aria-valuenow={progresso}
            aria-valuemin={0}
            aria-valuemax={100}
          >
            <div className="progresso__barra" style={{ width: `${progresso}%` }} />
          </div>
          <p className="andamento__status">
            {progresso < 100 ? `Enviando… ${progresso}%` : 'Registrando o job…'}
          </p>
        </>
      )}

      {emAndamento && etapa > 0 && (
        <p className="andamento__status">
          <span className="spinner" aria-hidden="true" />
          {etapa === 1 ? 'Na fila, aguardando um worker livre…' : 'Convertendo…'}
        </p>
      )}

      {falha && (
        <p className="alerta alerta--erro" role="alert">
          {falha}
        </p>
      )}

      {concluido && (
        <div className="andamento__resultado">
          <p>{duracao ? `Pronto em ${duracao}.` : 'Pronto!'}</p>
          {expirou ? (
            <div className="andamento__validade">
              O resultado expirou e foi removido. Envie o arquivo de novo para converter.
            </div>
          ) : (
            <>
              <a className="botao botao--primario" href={urlDownload(jobId)} download>
                Baixar resultado
              </a>
              {validade && (
                <div className="andamento__validade">Disponível para download até {validade}.</div>
              )}
            </>
          )}
        </div>
      )}

      {!emAndamento && (
        <div className="acoes">
          {erroConsulta && (
            <button type="button" className="botao botao--secundario" onClick={consultarDeNovo}>
              Consultar de novo
            </button>
          )}
          {onVoltarAoArquivo && !erroConsulta && (
            <button type="button" className="botao botao--secundario" onClick={onVoltarAoArquivo}>
              {concluido ? 'Outra conversão deste arquivo' : 'Ajustar e tentar de novo'}
            </button>
          )}
          <button type="button" className="botao botao--secundario" onClick={onRecomecar}>
            Converter outro arquivo
          </button>
        </div>
      )}
    </section>
  );
}
