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


class Withdrawal(BaseModel):
    wallet: str
    
    
class DeleteMessage(BaseModel):
    message: str
    
    
class SignedTTransactionBytesMessage(BaseModel):
    txBytes: Optional[str] = None


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
    lockedBalance: dict


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
    gas: List[dict]
    inputObjects: List[dict]
    txBytes: str


class AllStatisticsRead(BaseModel):
    totalAmountStaked: Decimal = Decimal(0)
    totalMatrixPoolGenerated: Decimal = Decimal(0)
    averageDailyReferral: int = 0
    totalAmountWithdrawn: Decimal
    totalAmountSentToGMP: Decimal
    totalDistributedFromGMP: Decimal

class TransactionDataResponse(BaseModel):
    messageVersion: str
    transaction: "TransactionData"
    sender: str
    gasData: List["GasData"] 
    

class TransactionData(BaseModel):
    kind: str
    inputs: List[dict]
    transactions: List[List[dict]]


class GasData(BaseModel):
    payment: List[dict]
    owner: str
    price: str
    budget: str


class TransactionResponse(BaseModel):
    data: TransactionDataResponse
    txSignatures: List[str]


class StatusResult(BaseModel):
    status: str
    
    
class GasUsed(BaseModel):
    computationCost: str
    storageCost: str
    storageRebate: str
    nonRefundableStorageFee: str
    
    
class Owner(BaseModel):
    AddressOwner: str


class Reference(BaseModel):
    objectId: str
    version: int
    digest: str


class ObjectChange(BaseModel):
    owner: Owner
    reference: Reference
    
    
class Effects(BaseModel):
    messageVersion: str
    status: StatusResult
    executedEpoch: str
    gasUsed: GasUsed
    transactionDigest: str
    mutated: List[ObjectChange]


class TransactionResponseData(BaseModel):
    digest: str
    transaction: TransactionResponse
    rawTransaction: str
    effects: Effects
    objectChanges: List[dict]
    
    
class UserBaseSchema(BaseModel):
    firstName: Annotated[Optional[str], constr(max_length=255)] = None  # First name with max length constraint
    lastName: Annotated[Optional[str], constr(max_length=255)] = None  # Last name with max length constraint
    phoneNumber: Annotated[Optional[str], constr(min_length=10, max_length=14)] = None  # Phone number with length constraints


class UserRead(UserBaseSchema):
    uid: uuid.UUID
    userId: str
    image: Optional[str] = None
    dob: Optional[date] = None

    isBlocked: bool = False
    isSuperuser: bool = False
    hasMadeFirstDeposit: bool = False

    rank: Optional[str]
    totalTeamVolume: Decimal = Decimal(0)
    totalReferrals: Decimal = Decimal(0)
    totalNetwork: Decimal = Decimal(0)

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
    level: int
    name: Optional[str]
    reward: Optional[Decimal] = Decimal(0.00)
    theirUserId: str
    userUid: uuid.UUID
    userId: str
    created: datetime

    class Config:
        from_attributes = True


class RegAndLoginResponse(BaseModel):
    message: str
    accessToken: str
    refreshToken: str
    user: "UserWithReferralsRead"


class AdminLogin(BaseModel):
    userId: str
    password: str
    
    
class UserCreateOrLoginSchema(BaseModel):
    userId: Annotated[str, constr(max_length=12, min_length=7)]
    firstName: Annotated[Optional[str], constr(max_length=255)] = None  # First name with max length constraint
    lastName: Annotated[Optional[str], constr(max_length=255)] = None  # Last name with max length constraint
    phoneNumber: Annotated[Optional[str], constr(min_length=10, max_length=14)
                           ] = None  # Phone number with length constraints
    image: Optional[str] = None

class UserLoginSchema(BaseModel):
    telegram_init_data: Optional[str] = None
    userId: Annotated[str, constr(max_length=12, min_length=7)]


class UserUpdateSchema(UserBaseSchema):
    dob: Optional[date] = None


class UserWithReferralsRead(BaseModel):
    user: UserRead
    referralsLv1: List[UserReferralRead]
    referralsLv2: List[UserReferralRead]
    referralsLv3: List[UserReferralRead]
    referralsLv4: List[UserReferralRead]
    referralsLv5: List[UserReferralRead]


class WalletBaseSchema(BaseModel):
    address: str
    # phrase: str
    # privateKey: str

    balance: Decimal = Decimal(0)
    earnings: Decimal = Decimal(0)
    availableReferralEarning: Decimal = Decimal(0)
    expectedRankBonus: Decimal = Decimal(0)
    weeklyRankEarnings: Decimal = Decimal(0)

    totalDeposit: Decimal = Decimal(0)
    totalTokenPurchased: Decimal = Decimal(0)
    totalRankBonus: Decimal = Decimal(0)
    totalFastBonus: Decimal = Decimal(0)
    totalWithdrawn: Decimal = Decimal(0)
    totalReferralEarnings: Decimal = Decimal(0)


class WalletRead(WalletBaseSchema):
    uid: uuid.UUID
    userUid: uuid.UUID = None

    createdAt: datetime

    class Config:
        from_attributes = True  # Allows loading from ORM models like SQLModel


class StakingBaseSchema(BaseModel):
    roi: Decimal = Decimal(0)
    deposit: Decimal = Decimal(0)


class StakingCreate(BaseModel):
    deposit: Decimal


class StakingRead(StakingBaseSchema):
    userUid: uuid.UUID

    start: Optional[datetime]
    end: Optional[datetime]
    nextRoiIncrease: Optional[datetime]

    class Config:
        from_attributes = True  # Allows loading from ORM models like SQLModel


class TokenMeterCreate(BaseModel):
    tokenAddress: str
    tokenPrivateKey: Optional[str] = None
    tokenPhrasee: Optional[str] = None
    totalCap: Decimal = Decimal(0)


class TokenMeterUpdate(BaseModel):
    tokenAddress: Optional[str] = None
    tokenPrivateKey: Optional[str] = None
    tokenPhrasee: Optional[str] = None
    totalCap: Optional[Decimal] = None


class SuiDollarRate(BaseModel):
    rate: Decimal
    
    
class TokenMeterRead(BaseModel):
    uid: uuid.UUID
    tokenAddress: Optional[str]
    tokenPhrase: Optional[str]
    tokenPrivateKey: Optional[str]
    totalCap: Decimal = Decimal(0)
    tokenPrice: Decimal = Decimal(0)
    percent_raised: Decimal = Decimal(0)
    totalAmountCollected: Decimal = Decimal(0)
    suiUsdPrice: Decimal = Decimal(0)
    totalDeposited: Decimal = Decimal(0)
    totalWithdrawn: Decimal = Decimal(0)
    totalSentToGMP: Decimal = Decimal(0)
    totalDistributedByGMP: Decimal = Decimal(0)

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
    raisedPoolAmount: Decimal = Decimal(0)
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
    userUid: uuid.UUID

    created: datetime
