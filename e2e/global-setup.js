const {execFileSync} = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');

const PASTA = path.join(__dirname, '.fixtures');
const VIDEO = path.join(PASTA, 'video.mp4');

const FFMPEG = [
    'ffmpeg -y -loglevel error',
    '-f lavfi -i testsrc=duration=30:size=640x360:rate=30',
    '-f lavfi -i sine=frequency=440:duration=30',
    '-c:v libx264 -preset ultrafast -c:a aac -shortest /tmp/e2e-video.mp4',
    '&& cat /tmp/e2e-video.mp4',
].join(' ');

module.exports = async () => {
    if (fs.existsSync(VIDEO)) {
        return;
    }
    fs.mkdirSync(PASTA, {recursive: true});
    // O FFmpeg do worker gera o vídeo: nem o runner nem a máquina local precisam dele.
    const video = execFileSync('docker', ['compose', 'exec', '-T', 'worker', 'sh', '-c', FFMPEG], {
        cwd: path.join(__dirname, '..'),
        maxBuffer: 50 * 1024 * 1024,
    });
    fs.writeFileSync(VIDEO, video);
};