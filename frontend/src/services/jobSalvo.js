const CHAVE = 'conversor:job';

export function salvarJob(dados) {
    try {
        sessionStorage.setItem(CHAVE, JSON.stringify(dados));
    } catch {
        // Sem storage (aba anônima, cota cheia): o F5 só volta para a tela inicial.
    }
}

export function carregarJob() {
    try {
        const dados = JSON.parse(sessionStorage.getItem(CHAVE));
        return dados?.jobId ? dados : null;
    } catch {
        return null;
    }
}

export function esquecerJob() {
    try {
        sessionStorage.removeItem(CHAVE);
    } catch {

    }
}