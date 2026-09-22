const test = require('node:test');
const assert = require('node:assert/strict');

const {
  parseVKVideoLink,
  parseYouTubeLink,
  parseRutubeLink,
  parsePLVideoLink,
  renderVideoFrame,
  renderSocialIcons,
} = require('./vendor-runtime');

test('parses VK video and clip links used by TOBIZ blocks', () => {
  assert.deepEqual(parseVKVideoLink('https://vkvideo.ru/video-228638078_456239059'), {
    owner_id: '-228638078', video_id: '456239059',
  });
  assert.deepEqual(parseVKVideoLink('https://vk.ru/clip-228638078_456239057'), {
    owner_id: '-228638078', video_id: '456239057',
  });
});

test('renders a VK iframe compatible with the vendor helper', () => {
  const html = renderVideoFrame('https://vk.ru/clip-228638078_456239057');
  assert.match(html, /<iframe/);
  assert.match(html, /video_ext\.php\?oid=-228638078&amp;id=456239057/);
  assert.match(html, /data-video-id="456239057"/);
});

test('parses common video providers', () => {
  assert.equal(parseYouTubeLink('https://youtu.be/dQw4w9WgXcQ'), 'dQw4w9WgXcQ');
  assert.equal(parseYouTubeLink('https://www.youtube.com/shorts/dQw4w9WgXcQ'), 'dQw4w9WgXcQ');
  assert.equal(parseRutubeLink('https://rutube.ru/video/abc_DEF-123/'), 'abc_DEF-123');
  assert.equal(parsePLVideoLink('https://plvideo.ru/watch?v=abc_DEF-123'), 'abc_DEF-123');
});

test('renders enabled social links without a browser jQuery runtime', () => {
  const html = renderSocialIcons({
    show_icons: 1, icons_figure: 'icon-circle',
    show_vk: 1, link_vk: 'https://vk.ru/example',
    show_tg: 1, link_tg: 'https://t.me/example',
  });
  assert.match(html, /social_icons_ng icon-circle/);
  assert.match(html, /sn-vk/);
  assert.match(html, /sn-telegram/);
});
