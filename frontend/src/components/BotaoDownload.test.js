import {fireEvent, render, screen, waitFor} from '@testing-library/react';
import {consultarJob} from '../services/api';
import BotaoDownload from './BotaoDownload';

jest.mock('../services/api', () => ({
    consultarJob: jest.fn(),
    mensagemDeErro: () => 'Sem resposta do servidor.',
    urlDownload: (id) => `/api/jobs/${id}/download`,
}));


let downloads;

function contarDownload(evento) {
    if (!evento.defaultPrevented) {
        downloads += 1;
    }
    evento.preventDefault();
}

beforeEach(() => {
    downloads = 0;
    consultarJob.mockReset();
    document.addEventListener('click', contarDownload);
});

afterEach(() => {
    document.removeEventListener('click', contarDownload);
});

test('libera o download quando o resultado ainda existe', async () => {
    consultarJob.mockResolvedValue({status: 'DONE', download_url: '/jobs/abc/download'});
    render(<BotaoDownload jobId="abc" onExpirado={jest.fn()}/>);

    fireEvent.click(screen.getByRole('link', {name: 'Baixar resultado'}));

    await waitFor(() => expect(downloads).toBe(1));
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
});

test('resultado removido avisa a tela em vez de baixar', async () => {
    consultarJob.mockResolvedValue({status: 'DONE', download_url: null});
    const onExpirado = jest.fn();
    render(<BotaoDownload jobId="abc" onExpirado={onExpirado}/>);

    fireEvent.click(screen.getByRole('link', {name: 'Baixar resultado'}));

    await waitFor(() => expect(onExpirado).toHaveBeenCalled());
    expect(downloads).toBe(0);
});

test('falha na consulta mostra o erro e não baixa', async () => {
    consultarJob.mockRejectedValue(new Error('rede'));
    render(<BotaoDownload jobId="abc" onExpirado={jest.fn()}/>);

    fireEvent.click(screen.getByRole('link', {name: 'Baixar resultado'}));

    expect(await screen.findByRole('alert')).toHaveTextContent('Sem resposta do servidor.');
    expect(downloads).toBe(0);
});