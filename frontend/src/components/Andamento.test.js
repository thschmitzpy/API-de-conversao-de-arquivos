import {act, fireEvent, render, screen} from '@testing-library/react';
import useJobPolling from '../hooks/useJobPolling';
import Andamento from './Andamento';

jest.mock('../hooks/useJobPolling', () => ({__esModule: true, default: jest.fn()}));

const DIA_MS = 24 * 60 * 60 * 1000;
const AGORA = new Date('2026-11-24T12:00:00Z');

function jobConcluido(expiraEmMs) {
    return {
        status: 'DONE',
        created_at: AGORA.toISOString(),
        finished_at: AGORA.toISOString(),
        expires_at: new Date(AGORA.getTime() + expiraEmMs).toISOString(),
        files_purged_at: null,
    };
}

function renderizar(polling, props = {}) {
    useJobPolling.mockReturnValue({consultarDeNovo: jest.fn(), ...polling});
    render(
        <Andamento
            nomeArquivo="foto.png"
            titulo="Converter para JPG"
            progresso={100}
            jobId="abc"
            erroEnvio={null}
            onVoltarAoArquivo={jest.fn()}
            onRecomecar={jest.fn()}
            {...props}
        />
    );
}

function renderizarConcluido(expiraEmMs) {
    renderizar({job: jobConcluido(expiraEmMs), erro: null});
}

function avancar(ms) {
    act(() => {
        jest.advanceTimersByTime(ms);
    });
}

beforeEach(() => {
    jest.useFakeTimers();
    jest.setSystemTime(AGORA);
});

afterEach(() => {
    jest.useRealTimers();
});

test('retenção acima de 24,8 dias não expira na hora', () => {
    renderizarConcluido(30 * DIA_MS);
    avancar(1000);
    expect(screen.getByRole('link', {name: 'Baixar resultado'})).toBeInTheDocument();

    avancar(29 * DIA_MS);
    expect(screen.getByRole('link', {name: 'Baixar resultado'})).toBeInTheDocument();

    avancar(DIA_MS);
    expect(screen.queryByRole('link')).not.toBeInTheDocument();
    expect(screen.getByText(/O resultado expirou/)).toBeInTheDocument();
});

test('resultado já vencido não mostra o download', () => {
    renderizarConcluido(-1000);
    expect(screen.queryByRole('link')).not.toBeInTheDocument();
});

test('erro de consulta oferece consultar de novo, não reenviar', () => {
    const consultarDeNovo = jest.fn();
    renderizar({job: {status: 'PROCESSING'}, erro: 'Erro inesperado (HTTP 502).', consultarDeNovo});

    fireEvent.click(screen.getByRole('button', {name: 'Consultar de novo'}));

    expect(consultarDeNovo).toHaveBeenCalled();
    expect(screen.queryByRole('button', {name: /tentar de novo/})).not.toBeInTheDocument();
});

test('job concluído permite outra conversão do mesmo arquivo', () => {
    const onVoltarAoArquivo = jest.fn();
    renderizar({job: jobConcluido(DIA_MS), erro: null}, {onVoltarAoArquivo});

    fireEvent.click(screen.getByRole('button', {name: 'Outra conversão deste arquivo'}));

    expect(onVoltarAoArquivo).toHaveBeenCalled();
});

test('job restaurado após F5 não oferece voltar ao arquivo', () => {
    renderizar({job: {status: 'FAILED', error_message: 'Arquivo inválido.'}, erro: null}, {onVoltarAoArquivo: null});

    expect(screen.getByRole('alert')).toHaveTextContent('Arquivo inválido.');
    expect(screen.queryByRole('button', {name: /tentar de novo/})).not.toBeInTheDocument();
    expect(screen.getByRole('button', {name: 'Converter outro arquivo'})).toBeInTheDocument();
});