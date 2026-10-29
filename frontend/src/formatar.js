export function formatarBytes(bytes) {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  const unidades = ['KB', 'MB', 'GB'];
  let valor = bytes / 1024;
  let indice = 0;
  while (valor >= 1024 && indice < unidades.length - 1) {
    valor /= 1024;
    indice += 1;
  }
  return `${valor.toLocaleString('pt-BR', { maximumFractionDigits: 1 })} ${unidades[indice]}`;
}

export function formatarDuracao(inicioIso, fimIso) {
  const ms = new Date(fimIso) - new Date(inicioIso);
  if (!Number.isFinite(ms) || ms < 0) {
    return null;
  }
  if (ms < 1000) {
    return 'menos de 1 s';
  }
  const segundos = Math.round(ms / 1000);
  if (segundos < 60) {
    return `${segundos} s`;
  }
  return `${Math.floor(segundos / 60)} min ${segundos % 60} s`;
}
