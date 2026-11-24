import {act, render, screen} from '@testing-library/react';
import useJobPolling from '../hooks/useJobPolling';
import Andamento from './Andamento';

jest.mock('../hooks/useJobPolling', () => ({__esModule: true, default: jest.fn()}));

const DIA_MS = 24 * 60 * 60 * 1000;
const AGORA = new Date('2026-11-24T12:00:00Z');

function renderizarConcluido(expiraEmMs) {
    useJobPolling.mockReturnValue({
        job: {
            status: 'DONE',
            created_at: AGORA.toISOString(),
            finished_at: AGORA.toISOString(),
            expires_at: new Date(AGORA.getTime() + expiraEmMs).toISOString(),
            files_purged_at: null,
        },
        erro: null,
    });
    render(
        <Andamento
            arquivo={{name: 'foto.png'}}
            opcao={{titulo: 'Converter para JPG'}}
            progresso={100}
            jobId="abc"
            erroEnvio={null}
            onTentarDeNovo={() => {
            }}
            onRecomecar={() => {
            }}
        />
    );
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