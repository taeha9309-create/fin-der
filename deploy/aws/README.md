# AWS EC2 배포 안내

fin-der MVP를 EC2 한 대에서 Docker Compose로 실행하는 절차입니다. 최초 배포에서는 EC2 Public IPv4로 확인하고, 정상 동작 후 Elastic IP와 HTTPS를 연결합니다.

## EC2 설정

- Region: Asia Pacific (Seoul), `ap-northeast-2`
- AMI: Ubuntu Server 24.04 LTS, x86_64
- Instance type: `t3.large` 권장, 최소 `t3.medium`
- Storage: gp3 30 GiB 이상
- Metadata access: AWS 역할을 사용하지 않으면 `Disabled`

Security Group은 TCP 22와 80을 관리자 본인의 공인 IP에만 허용합니다. HTTPS 구성 후 TCP 443을 필요한 범위에 개방합니다. MySQL과 Backend, Sandbox, AI 서비스 포트는 외부에 개방하지 않습니다.

## Docker 설치

```bash
sudo apt update
sudo apt install -y ca-certificates curl git
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "Types: deb" | sudo tee /etc/apt/sources.list.d/docker.sources
echo "URIs: https://download.docker.com/linux/ubuntu" | sudo tee -a /etc/apt/sources.list.d/docker.sources
echo "Suites: $(. /etc/os-release && echo ${UBUNTU_CODENAME:-$VERSION_CODENAME})" | sudo tee -a /etc/apt/sources.list.d/docker.sources
echo "Components: stable" | sudo tee -a /etc/apt/sources.list.d/docker.sources
echo "Architectures: $(dpkg --print-architecture)" | sudo tee -a /etc/apt/sources.list.d/docker.sources
echo "Signed-By: /etc/apt/keyrings/docker.asc" | sudo tee -a /etc/apt/sources.list.d/docker.sources
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker ubuntu
```

SSH 연결을 종료하고 다시 접속한 뒤 `docker version`과 `docker compose version`을 확인합니다.

## 프로젝트 실행

```bash
git clone https://github.com/taeha9309-create/fin-der.git
cd fin-der
cp .env.aws.example .env
nano .env
chmod 600 .env
docker compose config --quiet
docker compose up -d --build
docker compose ps
```

`.env`의 모든 `REPLACE_WITH_...` 값을 서로 다른 긴 비밀번호와 실제 Gemini API 키로 교체합니다. 브라우저에서는 `http://EC2_PUBLIC_IP`로 접속합니다.

서버 내부 상태 확인:

```bash
curl --fail http://127.0.0.1/health
curl --fail http://127.0.0.1:8080/health
curl --fail http://127.0.0.1:8081/health
curl --fail http://127.0.0.1:8001/health
curl --fail http://127.0.0.1:8002/health
curl --fail http://127.0.0.1:8003/health
docker compose logs --tail 100
```

중지는 `docker compose down`을 사용합니다. DB 볼륨까지 지우는 `docker compose down -v`는 사용하지 않습니다.
