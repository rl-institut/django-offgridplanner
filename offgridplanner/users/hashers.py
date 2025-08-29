from django.contrib.auth.hashers import BasePasswordHasher
from passlib.hash import bcrypt


class LegacyBCryptHasher(BasePasswordHasher):
    algorithm = "bcrypt_legacy"

    def verify(self, password, encoded):
        encoded = encoded.replace(self.algorithm, "")
        return bcrypt.verify(password, encoded)

    def encode(self, password, salt=None, iterations=None):
        return bcrypt.hash(password)

    def safe_summary(self, encoded):
        return {"hash": encoded}
