import {carregarJob, esquecerJob, salvarJob} from './jobSalvo';

const JOB = {jobId: 'abc', nomeArquivo: 'foto.png', titulo: 'Converter para JPG'};

afterEach(() => {
    sessionStorage.clear();
});

test('devolve o job salvo', () => {
    salvarJob(JOB);
    expect(carregarJob()).toEqual(JOB);
});

test('esquece o job', () => {
    salvarJob(JOB);
    esquecerJob();
    expect(carregarJob()).toBeNull();
});

test('conteúdo inválido no storage vira null', () => {
    sessionStorage.setItem('conversor:job', '{quebrado');
    expect(carregarJob()).toBeNull();

    sessionStorage.setItem('conversor:job', '{"nomeArquivo": "foto.png"}');
    expect(carregarJob()).toBeNull();
});