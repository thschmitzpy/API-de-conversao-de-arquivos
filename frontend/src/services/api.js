import axios from 'axios';

const api = axios.create({ baseURL: '/api' });

export function criarJob(arquivo, operation, parameters, onProgresso) {
  const form = new FormData();
  form.append('file', arquivo);
  form.append('operation', operation);
  form.append('parameters', JSON.stringify(parameters));

  return api
    .post('/jobs', form, {
      onUploadProgress: (evento) => {
        if (evento.total) {
          onProgresso(Math.round((evento.loaded / evento.total) * 100));
        }
      },
    })
    .then((resposta) => resposta.data);
}

export function consultarJob(jobId, signal) {
  return api.get(`/jobs/${jobId}`, { signal }).then((resposta) => resposta.data);
}

export function urlDownload(jobId) {
  return `/api/jobs/${jobId}/download`;
}

export function mensagemDeErro(erro) {
  const status = erro.response?.status;
  const detail = erro.response?.data?.detail;

  if (!erro.response) {
      return 'Sem resposta do servidor. Confira sua conexão e tente de novo.';
    }
    if (status === 429) {
      return 'Muitas requisições em pouco tempo. Aguarde um minuto e tente de novo.';
    }
    if (status === 401 || status === 403) {
      return 'O front não está autorizado na API (confira a CONVERSOR_API_KEY).';
    }
    if (status === 404) {
      return 'Esta conversão não foi encontrada. Ela pode ter sido removida.';
    }
    if (status === 413) {
      return 'O arquivo passa do limite de envio do servidor.';
    }
    // Nos 5xx o detail é interno (storage, fila) ou nem existe (página de erro do nginx).
    if (status >= 500) {
      return 'O servidor está com problemas no momento. Tente de novo em instantes.';
    }
    if (typeof detail === 'string') {
      return detail;
    }
    return `A requisição foi recusada (HTTP ${status}).`;
  }
