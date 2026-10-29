import useJobPolling from '../hooks/useJobPolling';
import { formatarDuracao } from '../formatar';
import { urlDownload } from '../services/api';

const ETAPAS = ['Envio', 'Na fila', 'Processando', 'Pronto'];

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
  arquivo,
  opcao,
  progresso,
  jobId,
  erroEnvio,
  onTentarDeNovo,
  onRecomecar,
}) {
  const { job, erro: erroConsulta } = useJobPolling(jobId);

  const erroJob = job?.status === 'FAILED' ? job.error_message || 'O processamento falhou.' : null;
  const falha = erroEnvio || erroConsulta || erroJob;
  const concluido = job?.status === 'DONE';
  const emAndamento = !falha && !concluido;
  const etapa = etapaAtual(jobId, job);
  const duracao = concluido ? formatarDuracao(job.created_at, job.finished_at) : null;

  return (
    <section className="painel andamento" aria-live="polite">
      <header className="andamento__cabecalho">
        <strong title={arquivo.name}>{arquivo.name}</strong>
        <span>{opcao.titulo}</span>
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
          <a className="botao botao--primario" href={urlDownload(jobId)} download>
            Baixar resultado
          </a>
        </div>
      )}

      {!emAndamento && (
        <div className="acoes">
          {falha && (
            <button type="button" className="botao botao--secundario" onClick={onTentarDeNovo}>
              Ajustar e tentar de novo
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
