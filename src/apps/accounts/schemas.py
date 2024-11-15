from decimal import Decimal
import uuid
from fastapi import File, UploadFile
from pydantic import AnyHttpUrl, BaseModel, EmailStr, Field, FileUrl, IPvAnyAddress, constr, model_validator, root_validator
from pydantic_extra_types.phone_numbers import PhoneNumber
from pydantic_extra_types.routing_number import ABARoutingNumber
from pydantic_extra_types.payment import PaymentCardBrand, PaymentCardNumber
from pydantic_extra_types.country import CountryInfo

from datetime import date, datetime
from typing import Optional, List, Annotated

from src.apps.accounts.enum import ActivityType


class Message(BaseModel):
    message: str
    error_code: str


class DeleteMessage(BaseModel):
    message: str


class AccessToken(BaseModel):
    message: str
    access_token: str
    user: Optional["UserRead"] = None


class Coin(BaseModel):
    coinType: str
    coinObjectId: str
    version: str
    digest: str
    balance: str
    previousTransaction: str


class CoinBalance(BaseModel):
    coinType: str
    coinObjectCount: int
    totalBalance: str
    lockedBalance: str


class MetaData(BaseModel):
    decimals: int
    name: str
    symbol: str
    description: str
    iconUrl: List[str]
    id: Optional[str]


class WithdrawEarning(BaseModel):
    wallet_address: str


class SuiTransferResponse(BaseModel):
    gas: List[str]
    inputObjects: List[str]
    txBytes: str


class AllStatisticsRead(BaseModel):
    totalAmountStaked: Decimal = 0.00
    totalMatrixPoolGenerated: Decimal = 0.00
    averageDailyReferral: int = 0
    totalAmountWithdrawn: Decimal
    totalAmountSentToGMP: Decimal
    totalDistributedFromGMP: Decimal


class UserBaseSchema(BaseModel):
    firstName: Annotated[Optional[str], constr(max_length=255)] = None  # First name with max length constraint
    lastName: Annotated[Optional[str], constr(max_length=255)] = None  # Last name with max length constraint
    phoneNumber: Annotated[Optional[str], constr(min_length=10, max_length=14)
                           ] = None  # Phone number with length constraints
    email: Optional[EmailStr] = None  # Email with validation


class UserRead(UserBaseSchema):
    uid: uuid.UUID
    userId: str
    image: Optional[str] = None
    dob: Optional[date] = None

    isBlocked: bool = False
    isSuperuser: bool = False
    hasMadeFirstDeposit: bool = False

    rank: Optional[str]
    totalTeamVolume: Decimal = 0
    totalReferrals: Decimal = 0
    totalNetwork: Decimal = 0

    age: Optional[int] = 0

    # Relationships
    wallet: Optional["WalletRead"]
    referrer: Optional["UserReferralRead"]
    staking: Optional["StakingRead"]

    joined: datetime = Field(default_factory=datetime.utcnow)
    updatedAt: datetime = Field(default_factory=datetime.utcnow)

    @staticmethod
    def get_rank_from_wallet(wallet: "WalletRead"):
        return wallet.rankTitle if wallet is not None else None

    @staticmethod
    def calculate_age(dob: Optional[datetime]) -> int:
        if dob:
            today = datetime.today().date()
            age = today.year - dob.year - (
                (today.month, today.day) < (dob.month, dob.day)
            )
            return age
        return 0

    @classmethod
    def from_orm(cls, user: "UserRead"):
        user_dict = user.model_dump()
        user_dict["age"] = cls.calculate_age(user.dob)
        return cls(**user_dict)

    class Config:
        from_attributes = True  # Allows loading from ORM models like SQLModel


class UserReferralRead(BaseModel):
    uid: uuid.UUID
    userUid: uuid.UUID

    class Config:
        from_attributes = True


class RegAndLoginResponse(BaseModel):
    message: str
    accessToken: str
    refreshToken: str
    user: "UserWithReferralsRead"


class UserCreateOrLoginSchema(BaseModel):
    telegram_init_data: str
    userId: Annotated[str, constr(max_length=12, min_length=7)]
    firstName: Annotated[Optional[str], constr(max_length=255)] = None  # First name with max length constraint
    lastName: Annotated[Optional[str], constr(max_length=255)] = None  # Last name with max length constraint
    phoneNumber: Annotated[Optional[str], constr(min_length=10, max_length=14)
                           ] = None  # Phone number with length constraints
    image: Optional[str] = None


class UserUpdateSchema(UserBaseSchema):
    dob: Optional[date] = None


class UserLevelReferral(BaseModel):
    userId: str
    referralName: str
    referralId: int
    totalStake: Decimal = 0.00
    level: int
    reward: Decimal

    @staticmethod
    def calculate_bonus(level: int, totalStake: Decimal) -> Decimal:
        if level == 1:
            bonus = totalStake * 0.1
            return bonus
        elif level == 2:
            bonus = totalStake * 0.05
            return bonus
        elif level == 3:
            bonus = totalStake * 0.03
            return bonus
        elif level == 4:
            bonus = totalStake * 0.02
            return bonus
        elif level == 5:
            bonus = totalStake * 0.01
            return bonus
        return 0

    @classmethod
    def from_orm(cls, user: "UserLevelReferral"):
        user_dict = user.model_dump()
        user_dict["reward"] = cls.calculate_bonus(user.level, user.totalStake)
        return cls(**user_dict)


class UserWithReferralsRead(BaseModel):
    user: UserRead
    referralsLv1: List[UserLevelReferral]
    referralsLv2: List[UserLevelReferral]
    referralsLv3: List[UserLevelReferral]
    referralsLv4: List[UserLevelReferral]
    referralsLv5: List[UserLevelReferral]


class WalletBaseSchema(BaseModel):
    address: str
    phrase: str
    privateKey: str

    balance: Decimal = 0.00
    earnings: Decimal = 0.00
    availableReferralEarning: Decimal = 0.00
    expectedRankBonus: Decimal = 0.00
    weeklyRankEarnings: Decimal = 0.00

    totalDeposit: Decimal = 0.00
    totalTokenPurchased: Decimal = 0.00
    totalRankBonus: Decimal = 0.00
    totalFastBonus: Decimal = 0.00
    totalWithdrawn: Decimal = 0.00
    totalReferralEarnings: Decimal = 0.00


class WalletRead(WalletBaseSchema):
    uid: uuid.UUID
    userUid: uuid.UUID = None

    createdAt: datetime

    class Config:
        from_attributes = True  # Allows loading from ORM models like SQLModel


class StakingBaseSchema(BaseModel):
    roi: Decimal = 0.00
    deposit: Decimal = 0.00


class StakingCreate(BaseModel):
    deposit: Decimal


class StakingRead(StakingBaseSchema):
    userUid: uuid.UUID

    start: Optional[datetime]
    end: Optional[datetime]
    # nextRoiIncrease: datetime

    class Config:
        from_attributes = True  # Allows loading from ORM models like SQLModel


class TokenMeterCreate(BaseModel):
    tokenAddress: str
    tokenPrivateKey: Optional[str] = None
    tokenPhrasee: Optional[str] = None
    totalCap: Decimal = 0.00


class TokenMeterUpdate(BaseModel):
    tokenAddress: Optional[str] = None
    tokenPrivateKey: Optional[str] = None
    tokenPhrasee: Optional[str] = None
    totalCap: Optional[Decimal] = None


class TokenMeterRead(BaseModel):
    uid: uuid.UUID
    tokenAddress: Optional[str]
    tokenPhrase: Optional[str]
    tokenPrivateKey: Optional[str]
    totalCap: Decimal
    tokenPrice: Decimal
    suiUsdPrice: Decimal
    percent_raised: Decimal = 0.00

    @staticmethod
    def percentage_raised(token: "TokenMeterRead"):
        percentage = (token.totalAmountCollected / token.totalCap) * 100
        return percentage

    @classmethod
    def fro_orm(cls, token: "TokenMeterRead"):
        token_dict = token.model_dump()
        token_dict["percent_raised"] = cls.percentage_raised(token)
        return cls(**token_dict)


class MatrixPoolBase(BaseModel):
    raisedPoolAmount: Decimal = 0.00
    startDate: datetime
    endDate: datetime


class MatrixPoolRead(MatrixPoolBase):
    uid: uuid.UUID

    users: List["MatrixUsersRead"]
    totalReferrals: int = 0


class MatrixUserCreateUpdate(BaseModel):
    userId: str
    referralsAdded: int


class MatrixUsersRead(BaseModel):
    uid: uuid.UUID
    matrixPoolUid: uuid.UUID
    userId: str
    referralsAddes: int
    matrixearning: Decimal
    matrixShare: Decimal


class ActivitiesRead(BaseModel):
    uid: uuid.UUID

    activityType: ActivityType
    strDetail: Optional[str]
    amountDetail: Optional[Decimal]
    suiAmount: Optional[Decimal]
    userUid: str

    created: datetime
